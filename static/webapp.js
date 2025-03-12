document.addEventListener("DOMContentLoaded", () => {
  // Connect to the Socket.IO server
  const socket = io("https://30fc-115-97-235-240.ngrok-free.app");
  
  // Ensure non-empty username
  function getUsername() {
    let username = localStorage.getItem("username");
    while (!username || !username.trim()) {
      username = prompt("Enter your username:") || ("User" + Math.floor(Math.random() * 1000));
    }
    localStorage.setItem("username", username);
    return username;
  }
  
  const username = getUsername();
  
  // Retrieve or set personality
  let personality = localStorage.getItem("personality");
  if (!personality) {
    personality = prompt("Tell me about yourself (hobbies, interests, chat style):");
    if (personality) {
      localStorage.setItem("personality", personality);
      fetch("/store_personality", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, personality }),
      })
      .then(res => res.json())
      .then(data => console.log("Personality stored:", data))
      .catch(err => console.error("Error storing personality:", err));
    }
  }
  
  let currentReceiver = null;
  const messagesContainer = document.getElementById("messages");
  const contactsContainer = document.getElementById("contacts");
  const aiButton = document.getElementById("aiButton");
  const sendButton = document.getElementById("sendButton");
  const messageInput = document.getElementById("messageInput");
  
  // Join the chat
  socket.emit("join", { username, personality });
  
  // Update contacts list
  socket.on("user_list", (usersList) => {
    if (contactsContainer) {
      contactsContainer.innerHTML = "";
      usersList.forEach((user) => {
        if (user !== username) {
          const userElement = document.createElement("div");
          userElement.textContent = user;
          userElement.classList.add("contact-item");
          userElement.addEventListener("click", () => {
            currentReceiver = user;
            document.getElementById("chatRecipient").textContent = "Chat with " + user;
            messagesContainer.innerHTML = "";
            loadChatHistory(user);
          });
          contactsContainer.appendChild(userElement);
        }
      });
    }
  });
  
  // Load chat history
  function loadChatHistory(selectedUser) {
    const loadingMsg = document.createElement("div");
    loadingMsg.textContent = "Loading chat history...";
    loadingMsg.classList.add("loading-message", "system");
    messagesContainer.appendChild(loadingMsg);
    
    fetch("/get_chat_history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user1: username, user2: selectedUser })
    })
    .then(response => {
      if (!response.ok) throw new Error("Failed to load chat history");
      return response.json();
    })
    .then(messages => {
      messagesContainer.removeChild(loadingMsg);
      if (messages.length === 0) {
        const noMsg = document.createElement("div");
        noMsg.textContent = "No previous messages. Start a conversation!";
        noMsg.classList.add("system");
        messagesContainer.appendChild(noMsg);
        setTimeout(() => {
          if (noMsg.parentNode) {
            messagesContainer.removeChild(noMsg);
          }
        }, 3000);
      } else {
        messages.forEach(msg => {
          const type = (msg.sender === username) ? "sender" : "receiver";
          addMessage(`${msg.sender}: ${msg.content}`, type);
        });
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    })
    .catch(error => {
      if (loadingMsg.parentNode) messagesContainer.removeChild(loadingMsg);
      const errMsg = document.createElement("div");
      errMsg.textContent = "Could not load chat history.";
      errMsg.classList.add("system");
      messagesContainer.appendChild(errMsg);
      setTimeout(() => {
        if (errMsg.parentNode) {
          messagesContainer.removeChild(errMsg);
        }
      }, 3000);
    });
  }
  
  socket.on("receive_message", (data) => {
    // Only process messages addressed to the current user
    if (data.receiver === username) {
      const type = data.sender === username ? "sender" : "receiver";
      // Display just the raw message content
      addMessage(data.message, type);
      
      // Only speak the message if it wasn't sent by the current user
      if (data.sender !== username) {
        speakMessage(data.message);
      }
    }
  });
  
  sendButton.addEventListener("click", sendTextMessage);
  messageInput.addEventListener("keypress", (e) => { 
    if (e.key === "Enter") sendTextMessage();
  });
  
  function sendTextMessage() {
    if (!currentReceiver) {
      alert("Select a user before sending messages.");
      return;
    }
    const message = messageInput.value.trim();
    if (message) {
      socket.emit("send_message", { sender: username, receiver: currentReceiver, message });
      // Display the message as-is
      addMessage(message, "sender");
      messageInput.value = "";
    }
  }  
  
  // Helper to add a message bubble
  function addMessage(message, type) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message-bubble", type);
    msgDiv.textContent = message;
    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
  
  // Use browser's built-in TTS to speak the message on the receiver's device
  function speakMessage(message) {
    if ('speechSynthesis' in window) {
      speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(message);
      utterance.lang = "en-US";
      speechSynthesis.speak(utterance);
    }
  }
  
  // Voice recording logic
  let aiRecording = false;
  let aiMediaRecorder;
  let aiAudioChunks = [];
  
  aiButton.addEventListener("click", () => {
    if (!currentReceiver) {
      alert("Select a user before sending voice messages.");
      return;
    }
    
    if (!aiRecording) {
      // Start recording
      aiButton.classList.add("recording");
      aiButton.textContent = "Stop Recording";
      
      navigator.mediaDevices.getUserMedia({ audio: true })
      .then((stream) => {
        aiMediaRecorder = new MediaRecorder(stream);
        aiMediaRecorder.start();
        aiRecording = true;
        aiAudioChunks = [];
        
        aiMediaRecorder.addEventListener("dataavailable", (event) => {
          aiAudioChunks.push(event.data);
        });
        
        aiMediaRecorder.addEventListener("stop", () => {
          aiRecording = false;
          aiButton.classList.remove("recording");
          aiButton.textContent = "Voice";
          
          // Create a Blob from recorded chunks
          const audioBlob = new Blob(aiAudioChunks, { type: "audio/webm" });
          const formData = new FormData();
          formData.append("audio", audioBlob, "recording.webm");
          formData.append("username", username);
          
          const loadingMsg = document.createElement("div");
          loadingMsg.textContent = "Processing your voice...";
          loadingMsg.classList.add("loading-message", "system");
          messagesContainer.appendChild(loadingMsg);
          
          // Send audio to backend for transcription/AI processing
          fetch("/transcribe", {
            method: "POST",
            headers: { "X-Username": username },
            body: formData
          })
          .then(response => {
            if (!response.ok) throw new Error("Server error");
            return response.json();
          })
          .then(data => {
            messagesContainer.removeChild(loadingMsg);
            if (data.error) {
              addMessage("Error: " + data.error, "system");
            } else {
              // Instead of "Voice Command:" or "My AI:", just show user’s transcript & AI response
              addMessage(data.transcription, "sender");  // The raw transcript
              addMessage(data.llm_response, "sender");   // The AI-generated text
              
              // Send the AI response as a chat message
              socket.emit("send_message", {
                sender: username,
                receiver: currentReceiver,
                message: data.llm_response
              });
            }
          })
          .catch(err => {
            if (loadingMsg.parentNode) {
              messagesContainer.removeChild(loadingMsg);
            }
            addMessage("Error processing voice. Please try again.", "system");
          });
        });
      })
      .catch(err => {
        aiButton.classList.remove("recording");
        aiButton.textContent = "Voice";
        addMessage("Error: Could not access microphone.", "system");
      });
    } else if (aiMediaRecorder && aiMediaRecorder.state !== "inactive") {
      // Stop recording
      aiMediaRecorder.stop();
    }
  });
  
  // Handle connection issues
  socket.on("connect_error", () => addMessage("Connection to server failed.", "system"));
  socket.on("disconnect", () => addMessage("Disconnected from server. Trying to reconnect...", "system"));
  socket.on("reconnect", (attemptNumber) => {
    addMessage("Reconnected to server!", "system");
    socket.emit("join", { username, personality });
  });
});