import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import sys
import os
from auralis import TTS, TTSRequest
import nltk
from nltk.tokenize import sent_tokenize
from pydub import AudioSegment
import re

tts = TTS().from_pretrained('AstraMindAI/xttsv2')

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

def read_epub(epub_path):
    """
    Read an EPUB file and extract text content organized by chapters.
    
    Args:
        epub_path (str): Path to the EPUB file
        
    Returns:
        dict: Dictionary with chapter titles as keys and content as values
    """
    if not os.path.exists(epub_path):
        raise FileNotFoundError(f"EPUB file not found at {epub_path}")
        
    # Load the EPUB file
    book = epub.read_epub(epub_path)
    
    # Dictionary to store chapters
    chapters = {}
    
    def clean_text(content):
        """Remove HTML tags and clean up text"""
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text()
        # Remove extra whitespace and normalize line breaks
        return ' '.join(text.split())
    
    # Process each item in the book
    for item in book.get_items():
        # We only want the HTML documents
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # Try to extract title from the content
            content = item.get_content().decode('utf-8')
            soup = BeautifulSoup(content, 'html.parser')
            
            # Try to find chapter title
            title = None
            for heading in soup.find_all(['h1', 'h2', 'h3']):
                if heading.text.strip():
                    title = heading.text.strip()
                    break
            
            if not title:
                # Use item ID if no title found
                title = f"Chapter {item.id}"
            
            # Clean and store the chapter content
            chapter_content = clean_text(content)
            chapters[title] = chapter_content
    
    return chapters, book.get_metadata('DC', 'title')[0][0]

def wipe_temp_dir(temp_dir):
    """
    Deletes all files in the specified directory.
    """
    try:
        if not os.path.exists(temp_dir):
            print(f"Directory {temp_dir} does not exist.")
            return

        concat_wavs_to_mp3(temp_dir, "tempfile_output.mp3")
        
        for file in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file)
            
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Deleted: {file_path}")
            else:
                print(f"Skipping non-file: {file_path}")
        
        print(f"All files in {temp_dir} have been deleted.")
    except Exception as e:
        print(f"Error while wiping directory {temp_dir}: {e}")

def concat_wavs_to_mp3(input_dir, output_file):
    """
    Concatenate all .wav files in a directory into a single MP3.
    """
    # List all .wav files in the directory, sorted by filename
    wav_files = sorted(
        [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith('.wav')]
    )
    
    if not wav_files:
        print("No .wav files found in the directory.")
        return

    def extract_chapter_number(filename):
        match = re.search(r'chapter_(\d+)\.wav', filename)
        return int(match.group(1)) if match else float('inf')

    wav_files.sort(key=extract_chapter_number)
    
    print(f"Converting WAVs in: {input_dir}")
    for wav_file in os.listdir(input_dir):
        if wav_file.endswith('.wav'):
            wav_path = os.path.join(input_dir, wav_file)
            mp3_path = wav_path.replace('.wav', '.mp3')
            print(f"Converting {wav_file} to MP3...")
            audio = AudioSegment.from_wav(wav_path)
            audio.export(mp3_path, format="mp3")
            del audio  # Clear memory
    
    print(f"Concatenating MP3s from: {input_dir}")
    # Get and sort MP3 files
    mp3_files = [f for f in os.listdir(input_dir) if f.endswith('.mp3')]
    mp3_files.sort(key=lambda x: int(re.search(r'chapter_(\d+)', x).group(1)))
    
    # Read all MP3s
    segments = []
    for mp3_file in mp3_files:
        mp3_path = os.path.join(input_dir, mp3_file)
        print(f"Reading {mp3_file}...")
        segments.append(AudioSegment.from_mp3(mp3_path))
    
    # Concatenate and export
    print("Concatenating files...")
    final_audio = sum(segments)
    print(f"Exporting to {output_file}...")
    final_audio.export(output_file, format="mp3")
    print(f"Completed: Export to {output_file}!")


def main():
    if len(sys.argv) != 3:
        print("Usage: python main.py </path/to/file.epub> <voice.wav>")
        sys.exit(1)

    epub_path = sys.argv[1]
    voice = sys.argv[2]
    book_title = None
    success = False

    try:
        chapters, book_title = read_epub(epub_path)
        wipe_temp_dir('temp')
        i = 1
        # Print chapters and their content
        for title, content in chapters.items():
            try:
                request = TTSRequest(
                    speaker_files=[f"Voices/{voice}"],
                    text=content,
                )
                output = tts.generate_speech(request)
                output.save(f"temp/chapter_{i}.wav")
                i += 1
            except Exception as e:
                print(f"Error processing chapter {i}: {str(e)}")
                continue
        success = True
    except Exception as e:
        print(f"Error processing EPUB file: {str(e)}")

    # Run concatenation regardless of previous errors
    try:
        input_directory = "temp"
        # If book_title wasn't set due to error, use a default name
        output_mp3 = f"{book_title if book_title else 'audiobook'}.mp3"
        concat_wavs_to_mp3(input_directory, output_mp3)
        print(f"Successfully created {output_mp3}")
    except Exception as e:
        print(f"Error during audio concatenation: {str(e)}")
        sys.exit(1)

    # Only exit with error if both epub processing and concatenation failed
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()