document.addEventListener("DOMContentLoaded", () => {
  // Connect to the Socket.IO server
  const socket = io("https://b32d-115-97-0-225.ngrok-free.app");
  
  // Request notification permission on page load
  requestNotificationPermission();
  
  // Function to request notification permission
  function requestNotificationPermission() {
    if (!("Notification" in window)) {
      console.log("This browser does not support notifications");
      return;
    }
    
    if (Notification.permission !== "granted" && Notification.permission !== "denied") {
      Notification.requestPermission();
    }
  }
  
  // Show browser notification
  function showNotification(sender, message) {
    if (Notification.permission === "granted" && document.visibilityState !== "visible") {
      const notification = new Notification(`New message from ${sender}`, {
        body: message.substring(0, 100) + (message.length > 100 ? "..." : ""),
        icon: "/static/notification-icon.png"
      });
      
      notification.onclick = function() {
        window.focus();
        this.close();
      };
    }
  }
  
  // Store unread messages count for each user
  const unreadCounts = {};
  
  // Track if user is currently viewing the app
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && currentReceiver) {
      // Reset unread count when viewing messages from current receiver
      unreadCounts[currentReceiver] = 0;
      updateUnreadBadges();
    }
  });
  
  // Update unread badges in the contact list
  function updateUnreadBadges() {
    const contactElements = document.querySelectorAll(".contact-item");
    contactElements.forEach(el => {
      const usernameEl = el.querySelector("span:not(.status-indicator)");
      if (!usernameEl) return;
      
      const contactName = usernameEl.textContent;
      const unreadCount = unreadCounts[contactName] || 0;
      
      // Find or create the badge element
      let badgeEl = el.querySelector(".unread-badge");
      
      if (unreadCount > 0) {
        if (!badgeEl) {
          badgeEl = document.createElement("span");
          badgeEl.className = "unread-badge";
          el.appendChild(badgeEl);
        }
        badgeEl.textContent = unreadCount;
      } else if (badgeEl) {
        el.removeChild(badgeEl);
      }
    });
  }
  
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
  
  let currentReceiver = null;
  const messagesContainer = document.getElementById("messages");
  const contactsContainer = document.getElementById("contacts");
  const aiButton = document.getElementById("aiButton");
  const sendButton = document.getElementById("sendButton");
  const messageInput = document.getElementById("messageInput");
  
  // Settings elements
  const settingsButton = document.getElementById("settingsButton");
  const settingsMenu = document.getElementById("settingsMenu");
  const sttModelSelect = document.getElementById("sttModel");
  const ttsVoiceSelect = document.getElementById("ttsVoice");
  
  // Initialize settings from localStorage or set defaults
  function initSettings() {
    const savedSttModel = localStorage.getItem("sttModel") || "nova-2";
    const savedTtsVoice = localStorage.getItem("ttsVoice") || "FEMALE";
    
    sttModelSelect.value = savedSttModel;
    ttsVoiceSelect.value = savedTtsVoice;
    
    // Add event listeners for settings changes
    sttModelSelect.addEventListener("change", () => {
      localStorage.setItem("sttModel", sttModelSelect.value);
    });
    
    ttsVoiceSelect.addEventListener("change", () => {
      localStorage.setItem("ttsVoice", ttsVoiceSelect.value);
    });
  }
  
  // Toggle settings menu
  settingsButton.addEventListener("click", (e) => {
    e.stopPropagation();
    settingsMenu.classList.toggle("active");
  });
  
  // Close settings when clicking elsewhere
  document.addEventListener("click", (e) => {
    if (
      settingsMenu.classList.contains("active") && 
      !settingsMenu.contains(e.target) && 
      e.target !== settingsButton
    ) {
      settingsMenu.classList.remove("active");
    }
  });
  
  // Initialize settings
  initSettings();
  
  // Join the chat
  socket.emit("join", { username });
  
  // Initial load of all users when page loads
  fetchAllUsers();
  
  // Update user list when status changes
  socket.on("user_status_update", (data) => {
    updateUserList(data.all_users);
  });
  
  // Fetch all users from the server
  function fetchAllUsers() {
    fetch("/get_all_users")
      .then(response => {
        if (!response.ok) throw new Error("Failed to load users");
        return response.json();
      })
      .then(users => {
        updateUserList(users);
      })
      .catch(error => {
        console.error("Error fetching users:", error);
      });
  }
  
  // Update the user list with online/offline indicators
  function updateUserList(userList) {
    if (!contactsContainer) return;
    
    contactsContainer.innerHTML = "";
    
    // Sort users - online users first, then alphabetically
    userList.sort((a, b) => {
      if (a.is_online && !b.is_online) return -1;
      if (!a.is_online && b.is_online) return 1;
      return a.username.localeCompare(b.username);
    });
    
    userList.forEach((user) => {
      if (user.username !== username) {
        const userElement = document.createElement("div");
        userElement.classList.add("contact-item");
        
        // Add online/offline status indicator
        const statusIndicator = document.createElement("span");
        statusIndicator.classList.add("status-indicator");
        statusIndicator.classList.add(user.is_online ? "online" : "offline");
        
        // Create username element
        const usernameElement = document.createElement("span");
        usernameElement.textContent = user.username;
        
        // Add unread badge if there are unread messages
        const unreadCount = unreadCounts[user.username] || 0;
        if (unreadCount > 0) {
          const badge = document.createElement("span");
          badge.className = "unread-badge";
          badge.textContent = unreadCount;
          userElement.appendChild(badge);
        }
        
        // Add elements to contact item
        userElement.appendChild(statusIndicator);
        userElement.appendChild(usernameElement);
        
        userElement.addEventListener("click", () => {
          currentReceiver = user.username;
          document.getElementById("chatRecipient").textContent = user.username;
          messagesContainer.innerHTML = "";
          loadChatHistory(user.username);
          
          // Reset unread count when selecting a contact
          unreadCounts[user.username] = 0;
          updateUnreadBadges();
          
          // Highlight selected contact
          document.querySelectorAll(".contact-item").forEach(el => {
            el.classList.remove("selected");
          });
          userElement.classList.add("selected");
        });
        
        contactsContainer.appendChild(userElement);
      }
    });
  }
  
  // Load chat history
  function loadChatHistory(selectedUser) {
    const loadingMsg = document.createElement("div");
    loadingMsg.textContent = "Loading messages";
    loadingMsg.classList.add("loading-message");
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
        noMsg.textContent = "No messages yet";
        noMsg.classList.add("message-bubble", "system");
        messagesContainer.appendChild(noMsg);
        setTimeout(() => {
          if (noMsg.parentNode) {
            messagesContainer.removeChild(noMsg);
          }
        }, 3000);
      } else {
        // Reset all messages before displaying history
        messagesContainer.innerHTML = "";
        
        // Display messages with slight delay between each for better visual experience
        displayMessagesWithDelay(messages, 0);
      }
    })
    .catch(error => {
      if (loadingMsg.parentNode) messagesContainer.removeChild(loadingMsg);
      const errMsg = document.createElement("div");
      errMsg.textContent = "Could not load messages";
      errMsg.classList.add("message-bubble", "system");
      messagesContainer.appendChild(errMsg);
      setTimeout(() => {
        if (errMsg.parentNode) {
          messagesContainer.removeChild(errMsg);
        }
      }, 3000);
    });
  }
  
  // Display messages with a slight delay between each for better UX
  function displayMessagesWithDelay(messages, index) {
    if (index >= messages.length) {
      // All messages displayed
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
      return;
    }
    
    // Display current message without animations
    displayMessage(messages[index]);
    
    // Display next message with a short delay for smoother loading
    setTimeout(() => {
      displayMessagesWithDelay(messages, index + 1);
    }, 50);
  }
  
  socket.on("receive_message", (data) => {
    // Only process messages addressed to the current user AND not sent by the current user
    if (data.receiver === username && data.sender !== username) {
      // Create a message object similar to the one from the database
      const messageObj = {
        sender: data.sender,
        receiver: data.receiver,
        content: data.message,
        is_ai_response: false,
        is_voice_message: data.is_voice_message || false,
        timestamp: new Date().toISOString()
      };
      
      // Show notification for new message
      showNotification(data.sender, data.message);
      
      // Update unread count if not viewing this conversation
      if (currentReceiver !== data.sender || document.visibilityState !== "visible") {
        unreadCounts[data.sender] = (unreadCounts[data.sender] || 0) + 1;
        updateUnreadBadges();
      }
      
      // Only display the message if the sender is the current contact
      if (currentReceiver === data.sender) {
        // For voice messages, play the audio first, then show message
        if (data.is_voice_message) {
          // Show "listening" effect before the message appears
          showSystemMessage(`${data.sender} is speaking...`);
          
          // Play the voice message with browser's speech synthesis
          speakVoiceMessage(data.message, () => {
            // After voice playback is complete, display the message
            displayMessage(messageObj);
          });
        } else {
          // Regular message - display immediately
          displayMessage(messageObj);
        }
      }
    }
  });
  
  // Helper to display a message with appropriate styling
  function displayMessage(message) {
    const type = (message.sender === username) ? "sender" : "receiver";
    const msgDiv = document.createElement("div");
    
    // All messages use standard styling
    msgDiv.classList.add("message-bubble", type);
    
    // Just display the message without animation, regardless of type
    msgDiv.textContent = message.content;
    
    messagesContainer.appendChild(msgDiv);
    
    // Ensure scroll to bottom is executed after the DOM has updated
    setTimeout(() => {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 0);
    
    return msgDiv;
  }
  
  // Helper to create and display message elements
  function createMessageElement(content, type, senderName) {
    if (!content || content.trim() === "") return;
    
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message-bubble", type);
    msgDiv.textContent = content;
    
    messagesContainer.appendChild(msgDiv);
    
    // Ensure scroll to bottom is executed after the DOM has updated
    setTimeout(() => {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 0);
  }
  
  sendButton.addEventListener("click", sendTextMessage);
  messageInput.addEventListener("keypress", (e) => { 
    if (e.key === "Enter") sendTextMessage();
  });
  
  function sendTextMessage() {
    if (!currentReceiver) {
      showSystemMessage("Select a contact first");
      return;
    }
    const message = messageInput.value.trim();
    if (message) {
      socket.emit("send_message", { sender: username, receiver: currentReceiver, message });
      
      messageInput.value = "";
      
      // Reload chat history to show the sent message
      setTimeout(() => loadChatHistory(currentReceiver), 300);
    }
  }
  
  // Helper to display system messages
  function showSystemMessage(text) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message-bubble", "system");
    msgDiv.textContent = text;
    messagesContainer.appendChild(msgDiv);
    
    setTimeout(() => {
      if (msgDiv.parentNode) {
        messagesContainer.removeChild(msgDiv);
      }
    }, 3000);
  }
  
  // Play voice message audio and call the callback when done
  function speakVoiceMessage(message, callback) {
    if ('speechSynthesis' in window) {
      speechSynthesis.cancel(); // Cancel any ongoing speech
      
      const utterance = new SpeechSynthesisUtterance(message);
      utterance.lang = "en-US";
      
      // Set callback for when speech is complete
      utterance.onend = () => {
        if (callback && typeof callback === 'function') {
          callback();
        }
      };
      
      // Speak the message
      speechSynthesis.speak(utterance);
    } else {
      // If speech synthesis not available, just show the message
      if (callback && typeof callback === 'function') {
        callback();
      }
    }
  }
  
  // Voice recording logic
  let aiRecording = false;
  let aiMediaRecorder;
  let aiAudioChunks = [];
  
  aiButton.addEventListener("click", () => {
    if (!aiRecording) {
      // Start recording - no need to check for currentReceiver anymore
      aiButton.classList.add("recording");
      aiButton.querySelector("span").textContent = "Recording...";
      
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
          aiButton.querySelector("span").textContent = "Voice Message";
          
          // Create a Blob from recorded chunks
          const audioBlob = new Blob(aiAudioChunks, { type: "audio/webm" });
          processAudio(audioBlob);
        });
      })
      .catch(err => {
        aiButton.classList.remove("recording");
        aiButton.querySelector("span").textContent = "Voice Message";
        showSystemMessage("Microphone access denied");
      });
    } else if (aiMediaRecorder && aiMediaRecorder.state !== "inactive") {
      // Stop recording
      aiMediaRecorder.stop();
    }
  });
  
  // Function to process audio blob and send to server
  async function processAudio(audioBlob) {
    if (!username) {
      showSystemMessage("Please enter your username to continue");
      return;
    }
    
    // Create FormData and append audio file
    const formData = new FormData();
    formData.append("file", audioBlob, "recording.wav");
    
    // Add parameter to indicate if we should use name detection
    // If a receiver is already selected, we don't need name detection
    formData.append("use_name_detection", currentReceiver ? "false" : "true");
    
    // Show processing message
    const loadingMsg = document.createElement("div");
    loadingMsg.textContent = "Processing your voice";
    loadingMsg.classList.add("loading-message");
    messagesContainer.appendChild(loadingMsg);
    
    try {
      // Send audio to backend for transcription/AI processing
      const response = await fetch("/transcribe", {
        method: "POST",
        headers: { "X-Username": username },
        body: formData
      });
      
      if (!response.ok) {
        throw new Error("Server error: " + response.status);
      }
      
      const data = await response.json();
      messagesContainer.removeChild(loadingMsg);
      
      if (data.error) {
        showSystemMessage("Error: " + data.error);
        return;
      }
      
      // If a contact was already selected, use that contact
      // Otherwise use the detected receiver from the transcript
      const finalReceiver = currentReceiver || data.detected_receiver;
      
      if (!finalReceiver) {
        // More informative error message
        if (currentReceiver) {
          showSystemMessage(`Sending message to ${currentReceiver}`);
        } else {
          showSystemMessage("No recipient detected. Please select a contact or mention a name clearly.");
          return;
        }
      }
      
      // If a receiver was detected from transcript and it's different from current, update the UI
      if (!currentReceiver && data.detected_receiver) {
        // Find the contact and select it
        const contactElements = document.querySelectorAll(".contact-item");
        let foundContact = false;
        contactElements.forEach(el => {
          const usernameEl = el.querySelector("span:not(.status-indicator)");
          if (usernameEl && usernameEl.textContent === data.detected_receiver) {
            // Simulate clicking on this contact
            el.click();
            foundContact = true;
            let detectionType = "";
            if (data.detection_method === "ai") {
              detectionType = "AI detected";
            } else if (data.detection_method === "pattern") {
              detectionType = "Pattern detected";
            }
            showSystemMessage(`${detectionType} and sending to: ${data.detected_receiver}`);
          }
        });
        
        if (!foundContact) {
          showSystemMessage(`Contact '${data.detected_receiver}' not found in your contacts`);
          return;
        }
      }
      
      // Determine if this is a relay message (checking if AI reformatted it)
      const isRelayMessage = data.response && 
                           data.response.trim() !== "" && 
                           (data.response.includes("wants to know") || 
                            data.response.includes("wanted to") ||
                            data.response.includes("asked") ||
                            data.response.toLowerCase().includes("hey,") ||
                            data.response.toLowerCase().startsWith("hey"));
      
      // Always use the AI response if available, regardless of whether a user is selected
      if (data.response && data.response.trim() !== "") {
        // Send the AI-processed message to the recipient
        socket.emit("send_message", {
          sender: username,
          receiver: finalReceiver,
          message: data.response,
          is_voice_message: true
        });
      } else {
        // Fallback to original transcript only if no AI response is available
        socket.emit("send_message", {
          sender: username,
          receiver: finalReceiver,
          message: data.transcript,
          is_voice_message: true
        });
      }
      
      // Reload chat history to show the sent message
      setTimeout(() => loadChatHistory(finalReceiver), 300);
      
    } catch (error) {
      messagesContainer.removeChild(loadingMsg);
      showSystemMessage("Error: " + error.message);
      console.error("Error processing audio:", error);
    }
  }
  
  // Handle connection issues
  socket.on("connect_error", () => showSystemMessage("Connection failed"));
  socket.on("disconnect", () => showSystemMessage("Disconnected from server"));
  socket.on("reconnect", (attemptNumber) => {
    showSystemMessage("Reconnected to server");
    socket.emit("join", { username });
  });
});