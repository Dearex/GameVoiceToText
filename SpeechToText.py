from time import sleep

import speech_recognition
import sounddevice
import soundfile
import googletrans
import keyboard
import kthread
import queue
import timeit
import io

SAMPLE_RATE = 16000
stt = None

global recording
recording = False
global key_pressed
key_pressed = False

data_queue = queue.Queue()

recognizer = speech_recognition.Recognizer()
translator = googletrans.Translator()


# file_length, recognition_language, translation_language, display, record_key, open_chat_key, close_chat_key


def Setup(file_length, sleep_length, recognition_language, translation_language, display, record_key, open_chat_key, close_chat_key):
    # Tries to get the Language code with the set Languages
    try:
        recognition_language = googletrans.LANGCODES[recognition_language]
        translation_language = googletrans.LANGCODES[translation_language]
    except:
        pass

    if translation_language == "None":
        translation_language = None

    global stt

    # Creates a Thread for the Voice Recognition
    stt = kthread.KThread(
        target=lambda: Run(file_length, sleep_length / 1000, recognition_language, translation_language, display, record_key, open_chat_key, close_chat_key))
    stt.setDaemon(True)
    stt.start()


# Kills the thread
def Stop():
    global stt
    stt.kill()


def Run(file_length, sleep_length, recognition_language, translation_language, display, record_key, open_chat_key, close_chat_key):
    display.addItem(f"Started: \nLanguage ={recognition_language}\nTranslation = {translation_language}\n"
                    f"File Length = {file_length} sec")

    # setting up key tracking to avoid counting holding as multiple pressing
    global recording

    def change_recording(_):
        global key_pressed
        if not key_pressed:
            global recording
            recording = not recording
            key_pressed = True

    def change_key_pressed(_):
        global key_pressed
        key_pressed = False

    keyboard.on_press_key(record_key, change_recording)
    keyboard.on_release_key(record_key, change_key_pressed)

    while True:
        display.addItem(f"Waiting for Key Input {record_key}")
        keyboard.wait(record_key)
               
        # Create BytesIO to get a file-like object so no temporary file is needed
        audio_data = io.BytesIO()

        display.addItem("Recording")
        start = timeit.default_timer()

        # Write InputStream to file-like object and stop after timing or key press
        def callback(indata, frames, time, status):
            data_queue.put(indata.copy())

        with soundfile.SoundFile(audio_data, format="WAV", mode='w', samplerate=SAMPLE_RATE, channels=1) as file:
            with sounddevice.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=callback):
                while recording:
                    if timeit.default_timer() - start > file_length:
                        display.addItem("Max recording time elapsed...")
                        recording = False
                    file.write(data_queue.get())
                file.write(data_queue.get())

        # Loads the data to AudioFile...
        audio_data.seek(0)
        with speech_recognition.AudioFile(audio_data) as source:
            # Records the Audio in the recognizer
            audioData = recognizer.record(source)

        # ... and tries to recognize with google in the set Language
        try:
            text = recognizer.recognize_google(audioData, language=recognition_language)
        except BaseException as error:
            display.addItem(f"Error while recognizing: {error}")
            text = ""

        # Translates when a Translation language is set
        if translation_language is not None:
            # Tries to translate with google
            try:
                message = translator.translate(text, dest=translation_language).text
            except BaseException as error:
                display.addItem(f"Error while Translating: {error}")
                message = ""
        else:
            message = text

        # If a message was detected (and successfully processed), send it to the game
        if message:
            display.addItem(f"Sending: {message}")
            keyboard.press_and_release(open_chat_key)
            sleep(sleep_length)
            keyboard.write(message)
            sleep(sleep_length)
            keyboard.press_and_release(close_chat_key)
        else:
            display.addItem('Nothing to send')


