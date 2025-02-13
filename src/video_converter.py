import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.video_downloader import VideoDownloader
from src.audio_extractor import AudioExtractor
from src.transcription_manager import TranscriptionManager
from src.frame_processor import FrameProcessor
from src.output_generator import OutputGenerator

class VideoConverter:
    def __init__(self, config):
        self.config = config
        self.downloader = VideoDownloader(config['temp_dir'])
        self.audio_extractor = AudioExtractor(config['temp_dir'])
        self.transcriber = TranscriptionManager(config['transcription'])
        self.frame_processor = FrameProcessor(
            config['output_dir'],
            max_frames=config['video_processing']['max_frames'],
            mode=config['video_processing']['frame_mode'],
            blip_enabled=config['blip']['enabled']
        )
        self.output_generator = OutputGenerator(config['output_dir'])

    def convert(self, url):
        """Обрабатывает видео и конвертирует его в учебный материал"""
        video_path, title = self.downloader.download(url)
        audio_path = None
        frames = None

        try:
            with ThreadPoolExecutor() as executor:
                future_tasks = {
                    executor.submit(self.audio_extractor.extract, video_path): "audio",
                    executor.submit(self.frame_processor.process, video_path): "frames"
                }

                results = {}
                for future in as_completed(future_tasks):
                    task_name = future_tasks[future]
                    try:
                        results[task_name] = future.result()
                    except Exception as e:
                        print(f"Ошибка при обработке {task_name}: {e}")
                        raise
                
                audio_path = results.get("audio")
                frames = results.get("frames")

            segments = self.transcriber.transcribe(audio_path)
            result = self.output_generator.generate({
                'title': title,
                'segments': segments,
                'frames': frames
            })
            return result

        except Exception as e:
            print(f"Ошибка обработки видео: {e}")
            raise

        finally:
            # Удаление временных файлов
            if os.path.exists(video_path):
                os.remove(video_path)
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
