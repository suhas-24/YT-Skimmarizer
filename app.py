import os
import streamlit as st
import requests
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from yt_dlp import YoutubeDL

# Mistral API configuration
API_URL = "https://api.mistral.ai/v1"
API_KEY = "<your-auth>"
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# Deepgram API configuration
DEEPGRAM_API_KEY = "<your-auth>"
deepgram = DeepgramClient(DEEPGRAM_API_KEY)

# Function to download audio from YouTube video URL
def download_audio_from_url(url):
    videoinfo = YoutubeDL().extract_info(url=url, download=False)
    length = videoinfo['duration']
    filename = f"./audio/youtube/{videoinfo['id']}.mp3"
    options = {
        'format': 'bestaudio/best',
        'keepvideo': False,
        'outtmpl': filename,
    }
    with YoutubeDL(options) as ydl:
        ydl.download([videoinfo['webpage_url']])
    return filename, length

# Function to transcribe audio using Deepgram
def transcribe_audio(audio_path):
    try:
        print(audio_path)
        with open(audio_path, "rb") as file:
            buffer_data = file.read()
        payload: FileSource = {
            "buffer": buffer_data,
        }
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
        )
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)
        print(response.to_json(indent=4))
        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        return transcript
    except Exception as e:
        error_message = f"Exception: {e}"
        print(error_message)
        raise Exception(error_message)

# Function to summarize transcript using Mistral
def summarize_transcript(transcript):
    data = {
        "model": "open-mistral-7b",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that summarizes YouTube video transcripts. Provide a concise summary of the main points discussed in the video based on the given transcript. Do not include any additional information or opinions."},
            {"role": "user", "content": f"Please summarize the following YouTube video transcript:\n\n{transcript}\n\nSummary:"}
        ],
        "temperature": 0.7,
        "max_tokens": 4000
    }
    try:
        response = requests.post(f"{API_URL}/chat/completions", headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
        result = response.json()
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content'].strip()
        else:
            raise Exception("Unexpected response format from Mistral API")
    except requests.exceptions.RequestException as e:
        error_message = f"Error in Mistral API request: {e}"
        print(error_message)
        raise Exception(error_message)
    except (KeyError, IndexError) as e:
        error_message = f"Error in parsing Mistral API response: {e}"
        print(error_message)
        raise Exception(error_message)

# Function to display conversation history
def display_conversation_history():
    if st.session_state.conversation_history:
        st.markdown('<div class="header">Conversation History</div>', unsafe_allow_html=True)
        conversation_html = ""
        for chat in st.session_state.conversation_history:
            conversation_html += f'<div class="question">{chat["question"]}</div>'
            # Check if the answer contains bullet points or code
            if "\n-" in chat["answer"] or "\n*" in chat["answer"]:
                # Format bullet points
                answer_html = "<ul>"
                for line in chat["answer"].split("\n"):
                    if line.startswith("-") or line.startswith("*"):
                        answer_html += f"<li>{line[1:].strip()}</li>"
                    else:
                        answer_html += f"<p>{line}</p>"
                answer_html += "</ul>"
            elif "```" in chat["answer"]:
                # Format code
                answer_parts = chat["answer"].split("```")
                answer_html = ""
                for i, part in enumerate(answer_parts):
                    if i % 2 == 1:
                        answer_html += f'<pre><code>{part.strip()}</code></pre>'
                    else:
                        answer_html += f'<p>{part.strip()}</p>'
            else:
                answer_html = f'<p>{chat["answer"]}</p>'
            conversation_html += f'<div class="answer">{answer_html}</div>'
        st.markdown(f'<div class="conversation">{conversation_html}</div>', unsafe_allow_html=True)

# Streamlit app
def main():
    st.set_page_config(page_title="YouTube Skimmarizer", page_icon=":movie_camera:", layout="wide")

    # Custom CSS styles
    st.markdown(
        """
        <style>
        body {
            background-color: #f0f0f0;
        }
        .title {
            font-size: 36px;
            font-weight: bold;
            color: #989dbb;
            margin-bottom: 20px;
        }
        .header {
            font-size: 24px;
            font-weight: bold;
            color: #7F9F80;
            margin-top: 30px;
            margin-bottom: 10px;
        }
        .summary {
            font-size: 18px;
            line-height: 1.6;
            color: white;
            background-color: #121f2e;
            padding: 20px;
            border-radius: 5px;
        }
        .question {
            font-size: 18px;
            color: #c4b181;
            margin-bottom: 10px;
        }
        p {
            color: #d46a33;
        }
        .answer {
            font-size: 16px;
            line-height: 1.6;
            color: white;
            background-color: #121f2e;
            padding: 15px;
            border-radius: 5px;
        }
        .st-bb {
            color: rgb(129 127 127);
        }
        .stButton > button {
            background-color: #4c4a5b;
            color: white;
            font-size: 18px;
            padding: 10px 20px;
            border-radius: 5px;
            transition: background-color 0.3s ease;
        }
        .stButton > button:hover {
            background-color: #35374B;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="title">YouTube Skimmarizer</div>', unsafe_allow_html=True)

    # Initialize session state variables
    if "summary" not in st.session_state:
        st.session_state.summary = ""
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []

    # Get YouTube video URL from user
    video_url = st.text_input("Enter YouTube video URL and press Enter:")

    # Process Video button
    if st.button("Skimmarize"):
        if video_url and video_url != st.session_state.get("video_url"):
            st.session_state.video_url = video_url
            st.session_state.summary = ""
            st.session_state.conversation_history = []

            # Show progress bar
            progress_bar = st.progress(0)

            # Download audio from YouTube video
            progress_bar.progress(0)
            audio_path, length = download_audio_from_url(video_url)
            progress_bar.progress(33)

            # Transcribe audio using Deepgram
            try:
                transcript = transcribe_audio(audio_path)
                progress_bar.progress(66)
            except Exception as e:
                st.error(f"Failed to transcribe audio. Error: {str(e)}")
                return

            if transcript:
                # Summarize transcript using Mistral
                summary = summarize_transcript(transcript)
                st.session_state.summary = summary
                progress_bar.progress(100)

    if st.session_state.summary:
        # Display summary
        st.markdown('<div class="header">Video Summary</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="summary">{st.session_state.summary}</div>', unsafe_allow_html=True)

        # Conversational Q&A
        st.markdown('<div class="header">Ask a Question</div>', unsafe_allow_html=True)
        question = st.text_input("Enter your question about the video:", key="question_input")
        if question:
            # Generate answer using Mistral
            data = {
                "model": "open-mistral-7b",
                "messages": [
                    {"role": "system", "content": f"You are a helpful assistant that answers questions about YouTube videos based on the provided summary. Respond only to questions directly related to the content of the video summary. If the question is not relevant to the video summary or cannot be answered based on the information provided, politely inform the user that you cannot answer the question.\n\nVideo Summary:\n{st.session_state.summary}"},
                    {"role": "user", "content": question}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            }
            response = requests.post(f"{API_URL}/chat/completions", headers=headers, json=data)
            result = response.json()
            answer = result['choices'][0]['message']['content'].strip()
            # Update conversation history
            st.session_state.conversation_history.append({"question": question, "answer": answer})

        # Display conversation history
        display_conversation_history()

if __name__ == "__main__":
    if not DEEPGRAM_API_KEY:
        st.error("DEEPGRAM_API_KEY environment variable is not set.")
    elif not API_KEY:
        st.error("MISTRAL_API_KEY environment variable is not set.")
    else:
        main()
