document.addEventListener("DOMContentLoaded", () => {
  // Connect to the Socket.IO server
  const socket = io("https://56ba-115-97-0-225.ngrok-free.app");
  
  // Create chat container
  const chatContainer = document.querySelector(".chat-container");
  
  // Initially hide the chat interface
  if (chatContainer) {
    chatContainer.style.display = "none";
  }
  
  // Define global variables
  let username;
  let currentReceiver = null;
  let messagesContainer;
  let contactsContainer;
  let aiButton;
  let sendButton;
  let messageInput;
  let settingsButton;
  let settingsMenu;
  let sttModelSelect;
  let ttsVoiceSelect;
  let waveform;
  let listeningIndicator;
  let emptyStateContainer;
  
  // Voice recording variables
  let aiRecording = false;
  let aiMediaRecorder;
  let aiAudioChunks = [];
  
  // Store unread messages count for each user
  const unreadCounts = {};
  
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
    
    // If no username in storage, redirect to login page
    if (!username || !username.trim()) {
      window.location.href = "/login";
      return null;
    }
    
    return username;
  }
  
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
  
  // Get username and initialize app only if we have one
  const initializeApp = () => {
    username = getUsername();
    
    // If getUsername returned null, we're being redirected to login
    // So don't continue with initialization
    if (!username) {
      return;
    }
    
    // Show the chat interface
    if (chatContainer) {
      chatContainer.style.display = "flex";
    }
    
    // Initialize DOM elements
    messagesContainer = document.getElementById("messages");
    contactsContainer = document.getElementById("contacts");
    aiButton = document.getElementById("aiButton");
    sendButton = document.getElementById("sendButton");
    messageInput = document.getElementById("messageInput");
    waveform = document.getElementById("waveform");
    listeningIndicator = document.getElementById("listeningIndicator");
    emptyStateContainer = document.getElementById("emptyStateContainer");
    
    // Initialize empty state with waveform visualization
    if (emptyStateContainer) {
      emptyStateContainer.style.display = "flex";
    }
  
    // Settings elements
    settingsButton = document.getElementById("settingsButton");
    settingsMenu = document.getElementById("settingsMenu");
    sttModelSelect = document.getElementById("sttModel");
    ttsVoiceSelect = document.getElementById("ttsVoice");

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
    
    // Set up event handlers
    sendButton.addEventListener("click", sendTextMessage);
    messageInput.addEventListener("keypress", (e) => { 
      if (e.key === "Enter") sendTextMessage();
    });
    
    // Set up voice message recording
    aiButton.addEventListener("click", handleVoiceRecording);
    
    // Set up logout button
    const logoutButton = document.getElementById("logoutButton");
    if (logoutButton) {
      logoutButton.addEventListener("click", () => {
        // Clear username from localStorage
        localStorage.removeItem("username");
        
        // Disconnect socket before redirecting
        if (socket && socket.connected) {
          socket.disconnect();
        }
        
        // Redirect to login page
        window.location.href = "/login";
      });
    }
    
    // Ensure socket connection and join the chat
    if (socket) {
      if (!socket.connected) {
        socket.connect();
      }
      socket.emit("join", { username });
    }
    
    // Initial load of all users when page loads
    fetchAllUsers();
    
    // Update user list when status changes
    socket.on("user_status_update", (data) => {
      updateUserList(data.all_users);
    });
    
    // Listen for messages
    socket.on("receive_message", (data) => {
      // Create a message object similar to the one from the database
      const messageObj = {
        sender: data.sender,
        receiver: data.receiver,
        content: data.message,
        is_ai_response: false,
        is_voice_message: data.is_voice_message || false,
        timestamp: new Date().toISOString()
      };

      // Case 1: Message from another user to the current user
      if (data.receiver === username && data.sender !== username) {
        // Show notification for new message
        showNotification(data.sender, data.message);
        
        // Update unread count if not viewing this conversation
        if (currentReceiver !== data.sender || document.visibilityState !== "visible") {
          unreadCounts[data.sender] = (unreadCounts[data.sender] || 0) + 1;
          updateUnreadBadges();
        }
        
        // Only display the message if the sender is the current contact
        if (currentReceiver === data.sender) {
          displayMessage(messageObj);
        }
      }
      // Case 2: Message sent by current user to someone else
      else if (data.sender === username && data.receiver === currentReceiver) {
        // Display message from current user
        displayMessage(messageObj);
      }
    });
  };
  
  // Start the app initialization
  initializeApp();
  
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
          
          // Hide empty state when a contact is selected
          if (emptyStateContainer) {
            emptyStateContainer.style.display = "none";
          }
        });
        
        contactsContainer.appendChild(userElement);
      }
    });
  }
  
  // Load chat history
  function loadChatHistory(selectedUser) {
    // Hide the empty state container when loading chat history
    if (emptyStateContainer) {
      emptyStateContainer.style.display = "none";
    }
    
    // Clear any existing content first
    messagesContainer.innerHTML = "";
    
    // Remove any existing loading messages first
    const existingLoadingMsgs = messagesContainer.querySelectorAll(".loading-message");
    existingLoadingMsgs.forEach(msg => {
      if (msg.parentNode) {
        messagesContainer.removeChild(msg);
      }
    });
    
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
      // Remove loading message
      if (loadingMsg.parentNode) {
        messagesContainer.removeChild(loadingMsg);
      }
      
      // Reset all messages before displaying history
      messagesContainer.innerHTML = "";
      
      if (messages.length === 0) {
        const noMsg = document.createElement("div");
        noMsg.textContent = "No messages yet";
        noMsg.classList.add("message-bubble", "system");
        messagesContainer.appendChild(noMsg);
        
        // Ensure even empty chat is scrolled to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        setTimeout(() => {
          if (noMsg.parentNode) {
            messagesContainer.removeChild(noMsg);
          }
        }, 3000);
      } else {
        // Display all messages at once without delay
        messages.forEach(message => {
          displayMessage(message);
        });
        
        // Scroll to bottom once
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    })
    .catch(error => {
      // Clean up the loading message
      if (loadingMsg.parentNode) {
        messagesContainer.removeChild(loadingMsg);
      }
      
      const errMsg = document.createElement("div");
      errMsg.textContent = "Could not load messages";
      errMsg.classList.add("message-bubble", "system");
      messagesContainer.appendChild(errMsg);
      
      // Ensure error message is visible
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
      
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
      return;
    }
    
    // Display all messages immediately without animation
    messages.forEach(message => {
      displayMessage(message);
    });
    
    // Scroll to bottom once after all messages are loaded
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
  
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
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return msgDiv;
  }
  
  function sendTextMessage() {
    if (!currentReceiver) {
      showSystemMessage("Select a contact first");
      return;
    }
    const message = messageInput.value.trim();
    if (message) {
      // Clear input first
      messageInput.value = "";
      
      // Create and display the message locally for immediate feedback
      const msgObj = {
        sender: username,
        receiver: currentReceiver,
        content: message,
        timestamp: new Date().toISOString()
      };
      
      // Display the message immediately
      displayMessage(msgObj);
      
      // Then send it to the server
      socket.emit("send_message", { sender: username, receiver: currentReceiver, message });
    }
  }
  
  // Helper to display system messages
  function showSystemMessage(text, isDurable = false) {
    // Verify messagesContainer exists
    if (!messagesContainer) {
      console.error("Messages container not found");
      return;
    }
    
    // Remove any existing system messages first
    const existingSystemMessages = messagesContainer.querySelectorAll(".message-bubble.system");
    existingSystemMessages.forEach(msg => {
      if (msg.parentNode) {
        messagesContainer.removeChild(msg);
      }
    });
    
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message-bubble", "system");
    msgDiv.textContent = text;
    messagesContainer.appendChild(msgDiv);
    
    // Ensure message is visible by scrolling
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Only auto-remove non-durable messages
    if (!isDurable) {
      setTimeout(() => {
        if (msgDiv.parentNode) {
          messagesContainer.removeChild(msgDiv);
        }
      }, 3000);
    }
    
    return msgDiv;
  }
  
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
    
    // Remove any existing loading messages and system messages
    const existingMessages = messagesContainer.querySelectorAll(".loading-message, .message-bubble.system");
    existingMessages.forEach(msg => {
      if (msg.parentNode) {
        messagesContainer.removeChild(msg);
      }
    });
    
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
      
      // Remove loading message
      if (loadingMsg.parentNode) {
        messagesContainer.removeChild(loadingMsg);
      }
      
      if (data.error) {
        showSystemMessage("Error: " + data.error, true);
        return;
      }
      
      // If a contact was already selected, use that contact
      // Otherwise use the detected receiver from the transcript
      const finalReceiver = currentReceiver || data.detected_receiver;
      
      if (!finalReceiver) {
        // Error - no recipient detected
        showSystemMessage("No recipient detected. Please select a contact or mention a name clearly.", true);
        return;
      }
      
      // If a receiver was detected from transcript and it's different from current, update the UI
      if (!currentReceiver && data.detected_receiver) {
        // Find the contact and select it
        const contactElements = document.querySelectorAll(".contact-item");
        let foundContact = false;
        contactElements.forEach(el => {
          const usernameEl = el.querySelector("span:not(.status-indicator)");
          if (usernameEl && usernameEl.textContent === data.detected_receiver) {
            // Simulate clicking on this contact - this will load chat history etc.
            el.click();
            foundContact = true;
          }
        });
        
        if (!foundContact) {
          showSystemMessage(`Contact '${data.detected_receiver}' not found in your contacts`, true);
          return;
        }
      }
      
      // Send message with the appropriate content
      const messageToSend = data.response && data.response.trim() !== "" 
                          ? data.response 
                          : data.transcript;
                          
      // Send the message
      socket.emit("send_message", {
        sender: username,
        receiver: finalReceiver,
        message: messageToSend,
        is_voice_message: true
      });
      
      // Don't display the message locally, as it will come back through the socket
      // The server will send it back to us and the receive_message handler will display it
      
    } catch (error) {
      if (loadingMsg.parentNode) {
        messagesContainer.removeChild(loadingMsg);
      }
      showSystemMessage("Error: " + error.message, true);
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
  
  // Function to handle voice recording
  function handleVoiceRecording() {
    if (!aiRecording) {
      // Start recording - no need to check for currentReceiver anymore
      aiButton.classList.add("recording");
      aiButton.querySelector("span").textContent = "Recording...";
      
      // Show listening indicator and animate waveform
      if (listeningIndicator) {
        listeningIndicator.style.display = "flex";
      }
      
      if (waveform) {
        waveform.classList.add("active");
      }
      
      // If no contact is selected, make sure empty state is visible
      if (!currentReceiver && emptyStateContainer) {
        emptyStateContainer.style.display = "flex";
      }
      
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
          
          // Hide listening indicator and stop waveform animation
          if (listeningIndicator) {
            listeningIndicator.style.display = "none";
          }
          
          if (waveform) {
            waveform.classList.remove("active");
          }
          
          // Create a Blob from recorded chunks
          const audioBlob = new Blob(aiAudioChunks, { type: "audio/webm" });
          processAudio(audioBlob);
        });
      })
      .catch(err => {
        aiButton.classList.remove("recording");
        aiButton.querySelector("span").textContent = "Voice Message";
        showSystemMessage("Microphone access denied");
        
        // Hide listening indicator and stop waveform animation
        if (listeningIndicator) {
          listeningIndicator.style.display = "none";
        }
        
        if (waveform) {
          waveform.classList.remove("active");
        }
      });
    } else if (aiMediaRecorder && aiMediaRecorder.state !== "inactive") {
      // Stop recording
      aiMediaRecorder.stop();
    }
  }
});