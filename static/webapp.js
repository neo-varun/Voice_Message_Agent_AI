document.addEventListener("DOMContentLoaded", () => {
  // Connect to the Socket.IO server.
  const socket = io("https://af4b-2409-40f4-28-567e-e4e3-dfd3-eb16-57f2.ngrok-free.app");
  
  // Retrieve or set a username
  let username = localStorage.getItem("username");
  if (!username) {
    username = prompt("Enter your username:");
    if (!username) username = "User" + Math.floor(Math.random() * 1000);
    localStorage.setItem("username", username);
    
    // Set join date for new users
    const joinDate = new Date().toLocaleDateString();
    localStorage.setItem("join_date", joinDate);
  }

  // Retrieve or set user personality
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
      .then(response => response.json())
      .then(data => console.log("Personality stored:", data))
      .catch(error => console.error("Error storing personality:", error));
    }
  }

  let currentReceiver = null;

  const messagesContainer = document.getElementById("messages");
  const aiButton = document.getElementById("aiButton");
  const sendButton = document.getElementById("sendButton");
  const messageInput = document.getElementById("messageInput");

  // Join chat with both username and personality
  socket.emit("join", { username, personality });

  // Update active user list
  socket.on("user_list", (usersList) => {
    const contactsContainer = document.getElementById("contacts");
    if (contactsContainer) {
      contactsContainer.innerHTML = "";
      usersList.forEach((user) => {
        if (user !== username) {
          const userElement = document.createElement("div");
          userElement.textContent = user;
          userElement.classList.add("contact-item");
          userElement.addEventListener("click", () => {
            currentReceiver = user;
            const chatRecipient = document.getElementById("chatRecipient");
            if (chatRecipient) {
              chatRecipient.textContent = "Chat with " + user;
            }
            messagesContainer.innerHTML = "";
          });
          contactsContainer.appendChild(userElement);
        }
      });
    }
  });

  // Handle messages
  socket.on("receive_message", (data) => {
    if (data.receiver && (data.receiver === username || data.sender === username)) {
      const bubbleType = data.sender === username ? "sender" : "receiver";
      addMessage(data.sender + ": " + data.message, bubbleType);
      if (data.sender !== username) speakMessage(data.message);
    }
  });

  // Handle sending text messages
  if (sendButton && messageInput) {
    sendButton.addEventListener("click", sendTextMessage);
    messageInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") sendTextMessage();
    });
  }

  function sendTextMessage() {
    if (!currentReceiver) {
      alert("Select a user before sending messages.");
      return;
    }
    
    const message = messageInput.value.trim();
    if (message) {
      socket.emit("send_message", {
        sender: username,
        receiver: currentReceiver,
        message: message
      });
      
      addMessage("You: " + message, "sender");
      messageInput.value = "";
    }
  }

  function addMessage(message, type) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message-bubble", type);
    msgDiv.textContent = message;
    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function speakMessage(message) {
    if ("speechSynthesis" in window) {
      speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(message);
      utterance.lang = "en-US";
      speechSynthesis.speak(utterance);
    }
  }

  let aiRecording = false;
  let aiMediaRecorder;
  let aiAudioChunks = [];

  if (aiButton) {
    aiButton.addEventListener("click", () => {
      if (!currentReceiver) {
        alert("Select a user before sending voice messages.");
        return;
      }

      if (!aiRecording) {
        aiButton.classList.add("recording");
        aiButton.textContent = "Stop AI Voice";
        
        navigator.mediaDevices
          .getUserMedia({ audio: true })
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
              aiButton.textContent = "AI Voice";
              
              const audioBlob = new Blob(aiAudioChunks, { type: "audio/webm" });
              const formData = new FormData();
              formData.append("audio", audioBlob, "ai_recording.webm");
              formData.append("username", username);

              const loadingMsg = document.createElement("div");
              loadingMsg.textContent = "Processing your voice...";
              loadingMsg.classList.add("loading-message", "system");
              messagesContainer.appendChild(loadingMsg);

              fetch("/transcribe", {
                method: "POST",
                headers: {
                  "X-Username": username  // Send username in header
                },
                body: formData
              })
                .then((response) => {
                  if (!response.ok) {
                    throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
                  }
                  return response.json();
                })
                .then((data) => {
                  messagesContainer.removeChild(loadingMsg);
                  
                  if (data.error) {
                    console.error("STT Error:", data.error);
                    addMessage("Error processing voice: " + data.error, "system");
                  } else {
                    const rawText = data.transcription;
                    addMessage("Voice Command: " + rawText, "sender");

                    const serverLLMOutput = data.llm_response;
                    addMessage("My AI: " + serverLLMOutput, "sender");

                    socket.emit("send_message", {
                      sender: username,
                      receiver: currentReceiver,
                      message: serverLLMOutput,
                    });
                  }
                })
                .catch((err) => {
                  if (loadingMsg.parentNode) {
                    messagesContainer.removeChild(loadingMsg);
                  }
                  console.error("Error in /transcribe fetch:", err);
                  addMessage("Error: Could not process voice. Please try again.", "system");
                });
            });
          })
          .catch((err) => {
            aiButton.classList.remove("recording");
            aiButton.textContent = "AI Voice";
            console.error("Microphone access error:", err);
            addMessage("Error: Could not access microphone.", "system");
          });
      } else {
        if (aiMediaRecorder && aiMediaRecorder.state !== "inactive") {
          aiMediaRecorder.stop();
        }
      }
    });
  }

  // Handle connection errors
  socket.on("connect_error", (error) => {
    console.error("Connection error:", error);
    addMessage("Connection to server failed. Please refresh the page.", "system");
  });

  socket.on("disconnect", () => {
    console.log("Disconnected from server");
    addMessage("Disconnected from server. Trying to reconnect...", "system");
  });

  socket.on("reconnect", (attemptNumber) => {
    console.log(`Reconnected after ${attemptNumber} attempts`);
    addMessage("Reconnected to server!", "system");
    socket.emit("join", { username, personality });
  });
});