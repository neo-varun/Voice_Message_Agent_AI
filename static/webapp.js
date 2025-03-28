document.addEventListener("DOMContentLoaded", () => {
  // Connect to the Socket.IO server
  const socket = io(window.location.origin);
  
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
  
  // Conversation state for voice assistant
  let inConversation = false;
  let voiceConvoTimeout = null;
  
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
        badgeEl.textContent = unreadCount > 9 ? "9+" : unreadCount;
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
    waveform = document.getElementById("waveform");
    listeningIndicator = document.getElementById("listeningIndicator");
    
    // Voice UI elements
    const voiceStatus = document.getElementById("voiceStatus");
    const messagePreview = document.getElementById("messagePreview");
    const previewContent = document.getElementById("previewContent");
    const sendPreviewButton = document.getElementById("sendPreviewButton");
    const viewHistoryButton = document.getElementById("viewHistoryButton");
    
    // Initialize the send preview button
    if (sendPreviewButton) {
      sendPreviewButton.addEventListener("click", sendFinalMessage);
    }
    
    // Initialize the view history button
    if (viewHistoryButton) {
      viewHistoryButton.addEventListener("click", function() {
        // Toggle message history display
        if (messagesContainer.style.display === "none") {
          // Show message history
          messagesContainer.style.display = "flex";
          viewHistoryButton.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px; vertical-align: text-bottom;">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            Hide Message History
          `;
          
          // Make the waveform container smaller
          if (waveform && waveform.parentElement) {
            waveform.parentElement.style.marginBottom = "0";
            waveform.parentElement.style.marginTop = "10px";
          }
          
          // Load the chat history for the selected user
          if (window.selectedUser) {
            loadChatHistory(window.selectedUser);
          }
        } else {
          // Hide message history
          messagesContainer.style.display = "none";
          viewHistoryButton.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px; vertical-align: text-bottom;">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            View Message History
          `;
          
          // Restore the waveform container
          if (waveform && waveform.parentElement) {
            waveform.parentElement.style.marginBottom = "";
            waveform.parentElement.style.marginTop = "";
          }
        }
      });
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
        
        // If message history is visible and this is the current contact, display the message
        if (messagesContainer.style.display !== "none" && window.selectedUser === data.sender) {
          displayMessage(messageObj);
        }
      }
      
      // Case 2: Message sent by current user to someone else
      else if (data.sender === username) {
        // If message history is visible and this is the current contact, display the message
        if (messagesContainer.style.display !== "none" && window.selectedUser === data.receiver) {
          displayMessage(messageObj);
        }
      }
    });
  };
  
  // Start the app initialization
  initializeApp();
  
  // Fetch all users from the server
  function fetchAllUsers() {
    console.log("Fetching all users...");
    fetch("/get_all_users")
      .then(response => {
        if (!response.ok) {
          console.error("Server returned error response:", response.status, response.statusText);
          throw new Error("Failed to load users");
        }
        return response.json();
      })
      .then(users => {
        console.log("Users fetched successfully:", users);
        updateUserList(users);
      })
      .catch(error => {
        console.error("Error fetching users:", error);
      });
  }
  
  // Add a function to calculate unread count
  function calculateUnreadCount(contactName) {
    return unreadCounts[contactName] || 0;
  }
  
  // Update the user list with online/offline indicators
  function updateUserList(userList) {
    const contactsContainer = document.getElementById("contacts");
    console.log("Updating user list, contacts container exists:", !!contactsContainer);
    
    if (!contactsContainer) {
      console.error("Contacts container not found in DOM");
      return;
    }
    
    // Clear the contacts list
    contactsContainer.innerHTML = "";
    
    console.log(`Processing ${userList.length} users for the contacts list`);
    
    // Sort users by online status and then by username
    userList.sort((a, b) => {
      if (a.is_online !== b.is_online) {
        return a.is_online ? -1 : 1; // Online users first
      }
      return a.username.localeCompare(b.username); // Then alphabetically
    });
    
    // Keep track of how many contacts we've added
    let contactsAdded = 0;
    
    // Add each user to the list
    userList.forEach(user => {
      // Skip the current user
      if (user.username === localStorage.getItem("username")) {
        console.log(`Skipping current user: ${user.username}`);
        return;
      }
      
      // Create contact item
      const contactItem = document.createElement("div");
      contactItem.className = "contact-item";
      contactItem.dataset.username = user.username;
      
      // Status indicator
      const statusIndicator = document.createElement("div");
      statusIndicator.className = user.is_online ? "status-indicator online" : "status-indicator offline";
      
      // Username
      const usernameSpan = document.createElement("span");
      usernameSpan.textContent = user.username;
      
      // Unread badge (if needed)
      const unreadCount = calculateUnreadCount(user.username);
        if (unreadCount > 0) {
        const unreadBadge = document.createElement("span");
        unreadBadge.className = "unread-badge";
        unreadBadge.textContent = unreadCount > 9 ? "9+" : unreadCount;
        contactItem.appendChild(unreadBadge);
        }
        
        // Add elements to contact item
      contactItem.appendChild(statusIndicator);
      contactItem.appendChild(usernameSpan);
      
      // Add click handler
      contactItem.addEventListener("click", function() {
        handleContactClick(this);
      });
      
      // If this is the current receiver, select it
      if (user.username === currentReceiver) {
        contactItem.classList.add("selected");
      }
      
      // Add to container
      contactsContainer.appendChild(contactItem);
      contactsAdded++;
    });
    
    console.log(`Added ${contactsAdded} contacts to the contacts list`);
  }
  
  // Load chat history
  function loadChatHistory(selectedUser) {
    if (!messagesContainer) return;
    
    // Clear existing messages
    messagesContainer.innerHTML = "";
    
    // Add loading indicator
    const loadingMsg = document.createElement("div");
    loadingMsg.textContent = "Loading messages";
    loadingMsg.classList.add("message-bubble", "system");
    messagesContainer.appendChild(loadingMsg);
    
    // Fetch message history
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
      messagesContainer.innerHTML = "";
      
      if (messages.length === 0) {
        // Display a "no messages" indicator
        const noMsg = document.createElement("div");
        noMsg.textContent = "No messages yet";
        noMsg.classList.add("message-bubble", "system");
        messagesContainer.appendChild(noMsg);
      } else {
        // Display each message
        messages.forEach(message => {
          displayMessage(message);
        });
      }
      
      // Scroll to bottom
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    })
    .catch(error => {
      // Show error message
      messagesContainer.innerHTML = "";
      
      const errMsg = document.createElement("div");
      errMsg.textContent = "Error loading messages";
      errMsg.classList.add("message-bubble", "system");
      messagesContainer.appendChild(errMsg);
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
    if (!messagesContainer) return;
    
    const type = (message.sender === username) ? "outgoing" : "incoming";
    const msgDiv = document.createElement("div");
    
    // Add appropriate classes based on message type
    msgDiv.classList.add("message-bubble", type);
    
    // Create container for message content
    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";
    contentDiv.textContent = message.content;
    
    // Create timestamp element
    const timestampDiv = document.createElement("div");
    timestampDiv.className = "message-timestamp";
    
    // Format the timestamp
    const msgDate = new Date(message.timestamp);
    const formattedDate = msgDate.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
    
    timestampDiv.textContent = formattedDate;
    
    // Add content and timestamp to message
    msgDiv.appendChild(contentDiv);
    msgDiv.appendChild(timestampDiv);
    
    messagesContainer.appendChild(msgDiv);
    
    // Scroll to bottom
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
    
    // Remove any existing system messages except recipient info
    document.querySelectorAll(".message-bubble.system:not(.recipient-info)").forEach(el => {
        el.parentNode.removeChild(el);
    });
    
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message-bubble", "system");
    if (!isDurable) {
        msgDiv.classList.add("temporary");
    }
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
    if (!audioBlob) return;

    try {
        // Create a FormData object to send the audio
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.wav');

        // Get the username
        const username = getUsername();

        // Add username as a header
        const headers = {
            'X-Username': username
        };

        // Add flags for continuing conversation
        formData.append('is_continuing', window.currentConversationState ? 'true' : 'false');
        formData.append('use_name_detection', (!window.selectedUser || window.currentConversationState?.ready_to_send) ? 'true' : 'false');
        
        // Add voice gender preference
        formData.append('voice_gender', localStorage.getItem('ttsVoice') || 'FEMALE');

        // Update voice status
        updateVoiceStatus("Processing your message...");
        
        // Hide message preview if visible
        document.getElementById('messagePreview').style.display = 'none';

        // Send to server
        const response = await fetch('/transcribe', {
            method: 'POST',
            headers: headers,
            body: formData
        });

        const data = await response.json();

        if (data.error) {
            updateVoiceStatus(`Error: ${data.error}`);
            return;
        }

        // Initialize conversation state if needed
        if (!window.currentConversationState) {
            window.currentConversationState = {
                transcript: [],
                ready_to_send: false,
                final_message: null,
                recipient: null
            };
        }

        // Add transcript to conversation
        window.currentConversationState.transcript.push(data.transcript);

        // Update voice status with transcript
        updateVoiceStatus(`You said: "${data.transcript}"`);

        // Play the audio response if available
        if (data.audio_response) {
            // Convert base64 to audio and play it
            const audio = new Audio(`data:audio/mp3;base64,${data.audio_response}`);
            await audio.play();
            
            // Update voice status with the AI response after audio plays
            updateVoiceStatus(data.response);
        }

        // Update recipient if detected
        if (data.detected_receiver && !window.currentConversationState.recipient) {
            window.currentConversationState.recipient = data.detected_receiver;
            
            // Update the active contact in the sidebar
            const contactElements = document.querySelectorAll('.contact-item');
            contactElements.forEach(element => {
                if (!element.querySelector('span:not(.status-indicator)')) return;
                const contactName = element.querySelector('span:not(.status-indicator)').textContent;
                if (contactName === data.detected_receiver) {
                    document.querySelectorAll('.contact-item.selected').forEach(el => el.classList.remove('selected'));
                    element.classList.add('selected');
                }
            });
            
            // Update the chat recipient header
            document.getElementById('chatRecipient').textContent = `Message to: ${data.detected_receiver}`;
        }

        // Store the final message if provided
        if (data.final_message) {
            window.currentConversationState.final_message = data.final_message;
        }

        // If conversation is complete, show the message preview
        if (data.is_final) {
            const finalMessage = data.final_message || data.transcript;
            
            // Check if this is just a confirmation message
            const sendCommands = [
                "send", "send it", "send now", "confirm", "yes", "that's it", 
                "yeah that's it", "yeah send it", "that's good", "looks good",
                "yes, send the message", "yes send the message"
            ];
            
            const messageLower = finalMessage.toLowerCase().trim();
            
            // Only consider it a confirmation if the message is very short (<30 chars)
            // or if it starts with a confirmation phrase
            const isShortMessage = messageLower.length < 30;
            const startsWithConfirmation = sendCommands.some(cmd => 
                messageLower.startsWith(cmd) || 
                messageLower.startsWith(cmd + " ") ||
                messageLower.startsWith(cmd + ",")
            );
            
            const isJustConfirmation = (isShortMessage || startsWithConfirmation) && 
                                    sendCommands.some(cmd => messageLower.includes(cmd));
            
            if (isJustConfirmation && window.currentConversationState.final_message) {
                // This is just a confirmation, send the previous message
                sendFinalMessage();
                return;
            }
            
            // Otherwise, store the message for sending later
            window.currentConversationState.ready_to_send = true;
            
            // IMPORTANT: Always use the AI-generated final_message rather than the transcript
            if (data.final_message) {
                window.currentConversationState.final_message = data.final_message;
            }
            
            // Show the message preview in the new UI
            const previewContent = document.getElementById('previewContent');
            previewContent.textContent = window.currentConversationState.final_message || "No message to send";
            
            // Update the preview header if we have a recipient
            const messagePreview = document.getElementById('messagePreview');
            const previewHeader = messagePreview.querySelector('h3');
            
            if (window.currentConversationState.recipient) {
                previewHeader.textContent = `Message to ${window.currentConversationState.recipient}`;
            } else {
                previewHeader.textContent = 'Message Preview';
            }
            
            // Show the preview
            messagePreview.style.display = 'block';
            
            // Update voice status
            updateVoiceStatus("Your message is ready to send. Press the Send button to confirm.");
        }
    } catch (error) {
        console.error('Error processing audio:', error);
        updateVoiceStatus(`Error: ${error.message || 'Failed to process audio'}`);
    }
}
  
  // Update the voice status display
  function updateVoiceStatus(message) {
    const voiceStatus = document.getElementById('voiceStatus');
    if (voiceStatus) {
        voiceStatus.textContent = message;
    }
  }
  
  // Function to send the final message when user confirms
  function sendFinalMessage() {
    // Check if we have a message ready to send
    if (!window.currentConversationState || !window.currentConversationState.final_message) {
        updateVoiceStatus("No message ready to send");
        return;
    }
    
    // Get the recipient - either from state or the current selected user
    const recipient = window.currentConversationState.recipient || window.selectedUser;
    
    // Ensure we have a recipient
    if (!recipient) {
        updateVoiceStatus("Please select a recipient first");
        return;
    }
    
    // Get the message - ALWAYS use the AI-generated final message
    const messageContent = window.currentConversationState.final_message;
    
    // Send the message via socket.io
    socket.emit("send_message", {
        sender: getUsername(),
        receiver: recipient,
        message: messageContent,
        is_voice_message: true
    });
    
    console.log("Sent message to:", recipient, "Content:", messageContent);
    
    // Update UI to show message sent
    updateVoiceStatus(`Message sent to ${recipient}`);
    
    // Hide the message preview
    document.getElementById('messagePreview').style.display = 'none';
    
    // Reset conversation state
    window.currentConversationState = null;
    
    // Reset the chat recipient header
    document.getElementById('chatRecipient').textContent = 'Voice Messaging';
    
    // If we weren't already in a chat with this contact, navigate to the chat
    if (window.selectedUser !== recipient) {
        // Find and click on the contact element
        const contactElements = document.querySelectorAll(".contact-item");
        contactElements.forEach(contactElement => {
            if (!contactElement.querySelector("span:not(.status-indicator)")) return;
            const contactUsername = contactElement.querySelector("span:not(.status-indicator)").textContent;
            if (contactUsername === recipient) {
                // Update selected contact
                window.selectedUser = recipient;
                document.querySelectorAll('.contact-item.selected').forEach(el => el.classList.remove('selected'));
                contactElement.classList.add('selected');
            }
        });
    }
  }
  
  // Display assistant message in the conversation
  function displayAssistantMessage(message) {
    // Get the messages container
    const messagesContainer = document.getElementById("messages");
    
    // First, clear any previous assistant messages if they exist
    const existingAssistantMessages = document.querySelectorAll(".message-bubble.assistant");
    existingAssistantMessages.forEach(msg => msg.remove());
    
    // Create the message bubble
    const msgDiv = document.createElement("div");
    
    // Style for assistant messages
    msgDiv.classList.add("message-bubble", "incoming", "assistant");
    msgDiv.style.backgroundColor = "rgba(99, 102, 241, 0.1)";
    msgDiv.style.color = "var(--primary-dark)";
    msgDiv.style.border = "1px solid rgba(99, 102, 241, 0.2)";
    msgDiv.style.maxWidth = "80%";
    
    // Add assistant icon
    const iconDiv = document.createElement("div");
    iconDiv.style.display = "flex";
    iconDiv.style.alignItems = "center";
    iconDiv.style.marginBottom = "6px";
    
    const iconSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    iconSvg.setAttribute("width", "16");
    iconSvg.setAttribute("height", "16");
    iconSvg.setAttribute("viewBox", "0 0 24 24");
    iconSvg.setAttribute("fill", "none");
    iconSvg.setAttribute("stroke", "currentColor");
    iconSvg.setAttribute("stroke-width", "2");
    iconSvg.setAttribute("stroke-linecap", "round");
    iconSvg.setAttribute("stroke-linejoin", "round");
    
    const micPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    micPath.setAttribute("d", "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z");
    
    const micPath2 = document.createElementNS("http://www.w3.org/2000/svg", "path");
    micPath2.setAttribute("d", "M19 10v2a7 7 0 0 1-14 0v-2");
    
    const micLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    micLine.setAttribute("x1", "12");
    micLine.setAttribute("y1", "19");
    micLine.setAttribute("x2", "12");
    micLine.setAttribute("y2", "22");
    
    iconSvg.appendChild(micPath);
    iconSvg.appendChild(micPath2);
    iconSvg.appendChild(micLine);
    
    const assistantLabel = document.createElement("span");
    assistantLabel.textContent = "Voice Assistant";
    assistantLabel.style.marginLeft = "6px";
    assistantLabel.style.fontSize = "13px";
    assistantLabel.style.fontWeight = "500";
    
    iconDiv.appendChild(iconSvg);
    iconDiv.appendChild(assistantLabel);
    
    // Message content
    const contentDiv = document.createElement("div");
    contentDiv.textContent = typeof message === 'string' ? message : message.content;
    
    msgDiv.appendChild(iconDiv);
    msgDiv.appendChild(contentDiv);
    
    messagesContainer.appendChild(msgDiv);
    
    // Ensure scroll to bottom is executed after the DOM has updated
    setTimeout(() => {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 100);
    
    return msgDiv;
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
        // Start recording
        aiButton.classList.add("recording");
        aiButton.querySelector("span").textContent = "Recording...";
        
        // Show listening indicator and animate waveform
        if (listeningIndicator) {
            listeningIndicator.style.display = "flex";
        }
        
        if (waveform) {
            waveform.classList.add("active");
        }
        
        // Update voice status
        updateVoiceStatus("Listening...");
        
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
            aiRecording = false;
            aiButton.classList.remove("recording");
            aiButton.querySelector("span").textContent = "Voice Message";
            updateVoiceStatus("Microphone access denied");
            
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

  // Handle contact click
  function handleContactClick(contactElement) {
    // Get the username from the contact element
    const contactUsername = contactElement.querySelector("span:not(.status-indicator)").textContent;
    
    // Remove selected class from all contacts
    document.querySelectorAll(".contact-item.selected").forEach(element => {
        element.classList.remove("selected");
    });
    
    // Add selected class to clicked contact
    contactElement.classList.add("selected");
    
    // Store selected user
    window.selectedUser = contactUsername;
    currentReceiver = contactUsername; // For backward compatibility with message notifications
    
    // Update chat header to show selected recipient
    document.getElementById("chatRecipient").textContent = `Message to: ${contactUsername}`;
    
    // Show the view history button
    const viewHistoryButton = document.getElementById("viewHistoryButton");
    if (viewHistoryButton) {
      viewHistoryButton.style.display = "inline-flex";
      // Reset button text in case it was changed
      viewHistoryButton.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px; vertical-align: text-bottom;">
        <circle cx="12" cy="12" r="10"></circle>
        <polyline points="12 6 12 12 16 14"></polyline>
      </svg>
      View Message History`;
    }
    
    // If message history is currently visible, load it for the new contact
    if (messagesContainer && messagesContainer.style.display !== "none") {
      loadChatHistory(contactUsername);
    } else {
      // Hide the messages container if it's visible
      if (messagesContainer) {
        messagesContainer.style.display = "none";
      }
    }
    
    // If we have an active conversation, update the recipient
    if (window.currentConversationState) {
        window.currentConversationState.recipient = contactUsername;
        
        // If we have a final message ready, update the preview
        if (window.currentConversationState.final_message && window.currentConversationState.ready_to_send) {
            // Update preview header
            const messagePreview = document.getElementById('messagePreview');
            const previewHeader = messagePreview.querySelector('h3');
            previewHeader.textContent = `Message to ${contactUsername}`;
            
            // Make sure the preview is visible
            messagePreview.style.display = 'block';
        }
    }
    
    // Update voice status
    updateVoiceStatus(`Ready to record message for ${contactUsername}`);
  }

  // Remove unneeded functions
  // sendTextMessage is not needed anymore since we're using voice only

  // Clear system messages function can be simplified
  function clearSystemMessages() {
    // Just update the voice status to default
    updateVoiceStatus("Press the microphone button to start recording");
  }
});