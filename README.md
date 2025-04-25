# Voice Message Agent AI

## Overview
This project is a **Voice Message Agent AI** built using **Flask**, **SocketIO**, and **OpenAI APIs**. It allows users to **communicate through voice messages** with an intelligent assistant that can **transcribe speech, detect message recipients, and generate responses**.

The application features a **real-time chat interface**, **voice message recording and playback**, and **AI-assisted message formatting** with **conversation context storage**.

## Features
- **Voice Message Recording & Transcription** – Uses OpenAI Whisper for accurate speech-to-text
- **Intelligent Recipient Detection** – Automatically identifies the intended recipient from message content
- **Text-to-Speech Responses** – Converts AI responses to audio using Google Cloud TTS
- **Conversation Context Awareness** – Stores conversation history in Pinecone for contextual responses
- **Real-Time Chat Interface** – SocketIO-powered messaging with online status indicators
- **Multi-User Support** – Create accounts and message any registered user
- **AI-Assisted Message Formatting** – Helps structure and improve voice messages

## Prerequisites

### API Keys
Before running the application, you must have the following API keys:

- **OpenAI API Key** – For speech transcription and AI responses
- **Google Cloud API Key** – For text-to-speech functionality
- **Pinecone API Key** – For conversation context storage
- **PostgreSQL Database** – For storing user data and messages

## Installation & Setup

### Create a Virtual Environment (Recommended)
It is recommended to create a virtual environment to manage dependencies:
```bash
python -m venv venv
```
Activate the virtual environment:
- **Windows:**  
  ```bash
  venv\Scripts\activate
  ```
- **macOS/Linux:**  
  ```bash
  source venv/bin/activate
  ```

### Install Dependencies
Ensure you have **Python 3.x** installed, then install the required packages:
```bash
pip install -r requirements.txt
```

### Environment Variables
Create a **.env** file in the root directory with the following variables:
```
OPENAI_API_KEY=your_openai_api_key
GOOGLE_APPLICATION_CREDENTIALS=path/to/google_credentials.json
PINECONE_API_KEY=your_pinecone_api_key
DATABASE_URL=postgresql://username:password@localhost:5432/voice_agent
SECRET_KEY=your_secret_key
```

### Run the Application
Start the Flask application:
```bash
python app.py
```
The application will be accessible at **http://127.0.0.1:8000**

## How the Program Works

### Voice Message Processing
- When a user **records a voice message**, the audio is sent to the server
- The app uses **OpenAI Whisper** to **transcribe the speech to text**
- An AI analysis **detects the intended recipient** from the message content
- The application uses **OpenAI GPT models** to process the message and generate appropriate responses
- Response text is converted back to speech using **Google Cloud TTS**

### Conversation Context Management
- The app stores conversation history in **Pinecone vector database**
- This allows the AI to **maintain context** between messages
- The system can **reference previous exchanges** for more coherent interactions
- Messages are also stored in a **PostgreSQL database** for persistent chat history

### Real-Time Messaging
- **Flask-SocketIO** enables **real-time communication** between users
- Users can see who is **currently online**
- Messages are delivered **instantly** to recipients
- Both text and voice messages are supported with **read receipts**

## Usage Guide

### Registration and Login
- Visit the login page to **create an account** or **sign in**
- Your username will be used to **identify you** in the system

### Sending Voice Messages
- Click the **microphone button** to start recording
- Speak your message, mentioning the **recipient's name**
- The AI will **transcribe** your message and **detect the recipient**
- Review the transcription and **send** the message

### Chatting with Users
- Select a user from the **contacts list**
- View your **conversation history**
- Send **text messages** or **voice messages**
- See when users are **online** and when messages are **read**

## Technologies Used
- **Python** & **Flask** (Backend)
- **SocketIO** (Real-time Communication)
- **OpenAI APIs** (Speech Transcription & NLP)
- **Google Cloud TTS** (Text-to-Speech)
- **Pinecone** (Vector Database for Conversation Context)
- **PostgreSQL** (Relational Database)
- **HTML/CSS/JavaScript** (Frontend)

## License
This project is licensed under the **MIT License**.

## Author
Developed by **Varun**. Feel free to connect with me on:
- **Email:** darklususnaturae@gmail.com 