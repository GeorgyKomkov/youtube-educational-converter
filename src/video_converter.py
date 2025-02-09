import os
from .video_downloader import VideoDownloader
from .audio_extractor import AudioExtractor
from .transcription_manager import TranscriptionManager
from .frame_processor import FrameProcessor
from .output_generator import OutputGenerator

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
        video_path, title = self.downloader.download(url)
        audio_path = self.audio_extractor.extract(video_path)
        segments = self.transcriber.transcribe(audio_path)
        frames = self.frame_processor.process(video_path)
        result = self.output_generator.generate({
            'title': title,
            'segments': segments,
            'frames': frames
        })
        # Очистка временных файлов
        os.remove(video_path)
        os.remove(audio_path)
        return result