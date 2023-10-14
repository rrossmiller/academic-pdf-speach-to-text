from pydub import AudioSegment
from glob import glob
from tqdm import tqdm
from google.cloud import texttospeech
import fitz
import re
import os, shutil


def get_text(pth):
    out = ""
    stop = False
    with fitz.open(pth) as doc:
        for page in doc:  # iterate the document pages
            text: str = page.get_text()  # get plain text encoded as UTF-8
            lines = text.split("\n")
            for l in lines:
                # remove line numbers
                if not l.isalnum():
                    out += l + " "

                # stop before the methodology.
                # There are a lot of formulas in the methodology... just read them
                if "79" in l or "Methodology" in l:
                    stop = True
                    break
            if stop:
                break

    assert len(out) > 0
    # remove reference annotations from audio
    out = re.sub(r"\[\d+[–,]?\d?\]", "", out)

    return out


def synthesize_text(text, fname="output.mp3"):
    """Synthesizes speech from the input string of text."""

    client = texttospeech.TextToSpeechClient()

    input_text = texttospeech.SynthesisInput(text=text)

    # Note: the voice can also be specified by name.
    # Names of voices can be retrieved with client.list_voices().
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Studio-O",
        # ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    response = client.synthesize_speech(
        request={"input": input_text, "voice": voice, "audio_config": audio_config}
    )

    # The response's audio_content is binary.
    with open(f"audio/{fname}", "wb") as out:
        out.write(response.audio_content)


if __name__ == "__main__":

    paths = glob("pdfs/*")
    for pth in paths:
        text = get_text(pth)
        if len(text.encode()) < 5000:
            synthesize_text(text)
        else:
            os.mkdir("audio")
            # do multiple passes over the text of LIM bytes each
            LIM = 4000
            END_TKN = "<END_TKN>"
            text += f" {END_TKN}"
            texts = ""
            bs = 0
            i = 0
            t = tqdm(text.split(" "))
            for w in t:
                # if the word does not break the 5kb threashold
                if len(w.encode()) + bs < LIM and w != END_TKN:
                    # add the word to the current text
                    texts += w + " "
                    bs += len(w.encode())
                    t.set_description(f"{bs} bytes")
                else:
                    # run the current text through synthesis
                    t.set_description(f"synthesizing {i}: {bs} bytes")

                    synthesize_text(texts, f"{i}.mp3")
                    i += 1
                    # start new text with current word
                    texts = w + " "
                    bs = len(w.encode())

            # concat the mp3s
            mp3s = glob("audio/*.mp3")
            output_file_name = pth.split("/")[1].split(".")[0]

            files = []
            for m in mp3s:
                files.append(AudioSegment.from_mp3(m))

            combined = files[0]
            for f in files[1:]:
                combined += f
            combined.export(f"{output_file_name}.mp3", format="mp3")

            # cleanup
            shutil.rmtree("audio", ignore_errors=True)

        # long text gen
        # with open("gcp.toml", "rb") as f:
        #     cfg = tomllib.load(f)["GCP"]
        #
        # project_id = cfg["project_id"]
        # location = cfg["region"]
        # bucket_name = cfg["bucket_name"]
        # output_file_name = pth.split("/")[1].split(".")[0]
        # print(project_id, bucket_name, location, output_file_name)
        # synthesize_long_text(
        #     text,
        #     project_id,
        #     location,
        #     f"gs://{bucket_name}/{output_file_name}.wav",
        # )

# def synthesize_long_text(text, project_id, location, output_gcs_uri):
#     """
#     Synthesizes long input, writing the resulting audio to `output_gcs_uri`.
#
#     Example usage: synthesize_long_audio('12345', 'us-central1', 'gs://{BUCKET_NAME}/{OUTPUT_FILE_NAME}.wav')
#
#     """
#
#     client = texttospeech.TextToSpeechLongAudioSynthesizeClient()
#
#     input = texttospeech.SynthesisInput(text=text)
#
#     audio_config = texttospeech.AudioConfig(
#         audio_encoding=texttospeech.AudioEncoding.LINEAR16
#     )
#
#     voice = texttospeech.VoiceSelectionParams(
#         language_code="en-US", name="en-US-Standard-A"
#     )
#
#     parent = f"projects/{project_id}/locations/{location}"
#
#     request = texttospeech.SynthesizeLongAudioRequest(
#         parent=parent,
#         input=input,
#         audio_config=audio_config,
#         voice=voice,
#         output_gcs_uri=output_gcs_uri,
#     )
#
#     operation = client.synthesize_long_audio(request=request)
#     # Set a deadline for your LRO to finish. 300 seconds is reasonable, but can be adjusted depending on the length of the input.
#     # If the operation times out, that likely means there was an error. In that case, inspect the error, and try again.
#     result = operation.result(timeout=300)
#     print(
#         "\nFinished processing, check your GCS bucket to find your audio file! Printing what should be an empty result:",
#         result,
#     )
