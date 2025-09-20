/* eslint-disable */
import React, { useState, useEffect, useRef } from "react";
import { MessageCircle, User, Send, Plus, LogOut, Menu, X, Bot } from "lucide-react";

const App = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [currentUser, setCurrentUser] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [message, setMessage] = useState("");
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // API base URL
  const API_BASE = "http://localhost:5100/api";

  // Auto scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversation?.messages]);

  // Fetch user conversations
  const fetchConversations = async (userId) => {
    try {
      const response = await fetch(`${API_BASE}/users/${userId}/conversations`);
      if (response.ok) {
        const data = await response.json();
        setConversations(data);
        if (data.length > 0 && !activeConversation) {
          // Load the first conversation
          await loadConversation(data[0].id);
        }
      }
    } catch (error) {
      console.error("Error fetching conversations:", error);
    }
  };

  // Load conversation details
  const loadConversation = async (conversationId) => {
    try {
      const response = await fetch(`${API_BASE}/conversations/${conversationId}`);
      if (response.ok) {
        const data = await response.json();
        setActiveConversation(data);
      }
    } catch (error) {
      console.error("Error loading conversation:", error);
    }
  };

  // Login function
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (response.ok) {
        const userData = await response.json();
        setCurrentUser(userData);
        setIsLoggedIn(true);
        await fetchConversations(userData.id);
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Login failed");
      }
    } catch (error) {
      console.error("Login error:", error);
      alert("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Logout function
  const handleLogout = () => {
    setIsLoggedIn(false);
    setCurrentUser(null);
    setUsername("");
    setPassword("");
    setConversations([]);
    setActiveConversation(null);
    setIsMenuOpen(false);
  };

  // Create new conversation
  const createNewConversation = async () => {
    if (!currentUser) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users/${currentUser.id}/conversations`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ title: "New Conversation" }),
      });

      if (response.ok) {
        const newConversation = await response.json();
        setConversations(prev => [newConversation, ...prev]);
        await loadConversation(newConversation.id);
      }
    } catch (error) {
      console.error("Error creating conversation:", error);
    } finally {
      setLoading(false);
      setIsMenuOpen(false);
    }
  };

  // Send message
  const sendMessage = async () => {
    if (!message.trim() || !activeConversation) {
      return;
    }

    setLoading(true);
    try {
      // Send user message
      const userMessageResponse = await fetch(`${API_BASE}/conversations/${activeConversation.id}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: message, sender: "user" }),
      });

      if (userMessageResponse.ok) {
        const userMessage = await userMessageResponse.json();

        // Update UI with user message
        const updatedConversation = {
          ...activeConversation,
          messages: [...activeConversation.messages, userMessage],
          title: activeConversation.messages.length === 1 ? message.slice(0, 20) + (message.length > 20 ? "..." : "") : activeConversation.title
        };
        setActiveConversation(updatedConversation);
        setMessage("");

        // Fetch updated conversation to get AI response
        await loadConversation(activeConversation.id);
      }
    } catch (error) {
      console.error("Error sending message:", error);
    } finally {
      setLoading(false);
    }
  };

  // Format timestamp
  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  // Login Page
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
          <div className="text-center mb-8">
            <div className="mx-auto bg-indigo-100 rounded-full p-4 w-16 h-16 flex items-center justify-center mb-4">
              <Bot className="w-8 h-8 text-indigo-600" />
            </div>
            <h1 className="text-3xl font-bold text-gray-800 mb-2">AI Assistant</h1>
            <p className="text-gray-600">Intelligent conversations, always at your service</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                placeholder="Enter username"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                placeholder="Enter password"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 text-white py-3 rounded-lg font-medium hover:bg-indigo-700 transition-colors focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
            >
              {loading ? "Logging in..." : "Login"}
            </button>
          </form>

          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-2">Demo accounts:</p>
            <p className="text-xs text-gray-500">Username: user1, Password: password123</p>
            <p className="text-xs text-gray-500">Username: user2, Password: password456</p>
          </div>
        </div>
      </div>
    );
  }

  // Main App
  return (
    <div className="h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setIsMenuOpen(true)}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <div className="flex items-center space-x-2">
            <div className="bg-indigo-100 rounded-full p-2">
              <Bot className="w-5 h-5 text-indigo-600" />
            </div>
            <h1 className="text-lg font-semibold text-gray-800">AI Assistant</h1>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <LogOut className="w-5 h-5 text-gray-600" />
        </button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        {isMenuOpen && (
          <div className="fixed inset-0 z-50 lg:relative lg:inset-auto lg:z-auto">
            <div className="absolute inset-0 bg-black bg-opacity-50 lg:hidden" onClick={() => setIsMenuOpen(false)} />
            <div className="absolute left-0 top-0 h-full w-80 bg-white shadow-xl lg:relative lg:shadow-none z-10">
              <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-800">Conversations</h2>
                <button
                  onClick={() => setIsMenuOpen(false)}
                  className="lg:hidden p-2 rounded-lg hover:bg-gray-100"
                >
                  <X className="w-5 h-5 text-gray-600" />
                </button>
              </div>

              <div className="p-4">
                <button
                  onClick={createNewConversation}
                  disabled={loading}
                  className="w-full bg-indigo-600 text-white py-3 rounded-lg font-medium hover:bg-indigo-700 transition-colors flex items-center justify-center space-x-2 mb-4 disabled:opacity-50"
                >
                  <Plus className="w-4 h-4" />
                  <span>New Conversation</span>
                </button>
              </div>

              <div className="flex-1 overflow-y-auto">
                {conversations.map((conversation) => (
                  <div
                    key={conversation.id}
                    onClick={() => {
                      loadConversation(conversation.id);
                      setIsMenuOpen(false);
                    }}
                    className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors ${
                      activeConversation?.id === conversation.id ? "bg-indigo-50 border-l-4 border-l-indigo-500" : ""
                    }`}
                  >
                    <div className="flex items-start space-x-3">
                      <MessageCircle className="w-5 h-5 text-gray-400 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-gray-900 truncate">{conversation.title}</h3>
                        <p className="text-sm text-gray-500 truncate">
                          {conversation.preview || "New conversation"}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-4 border-t border-gray-200">
                <div className="flex items-center space-x-3">
                  <div className="bg-gray-200 rounded-full p-2">
                    <User className="w-4 h-4 text-gray-600" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">{currentUser?.name}</p>
                    <p className="text-sm text-gray-500">@{currentUser?.username}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col">
          {activeConversation ? (
            <>
              {/* Chat Header */}
              <div className="bg-white border-b border-gray-200 px-4 py-3">
                <h2 className="font-semibold text-gray-800">{activeConversation.title}</h2>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {activeConversation.messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-xs lg:max-w-md px-4 py-3 rounded-2xl ${
                        msg.sender === "user"
                          ? "bg-indigo-600 text-white rounded-br-md"
                          : "bg-white text-gray-800 border border-gray-200 rounded-bl-md shadow-sm"
                      }`}
                    >
                      <p className="text-sm">{msg.text}</p>
                      <p className={`text-xs mt-1 ${msg.sender === "user" ? "text-indigo-100" : "text-gray-500"}`}>
                        {formatTime(msg.created_at)}
                      </p>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              {/* Input Area */}
              <div className="bg-white border-t border-gray-200 p-4">
                <div className="flex items-center space-x-3">
                  <input
                    type="text"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyPress={(e) => e.key === "Enter" && !loading && sendMessage()}
                    disabled={loading}
                    className="flex-1 px-4 py-3 border border-gray-300 rounded-full focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all disabled:opacity-50"
                    placeholder="Type a message..."
                  />
                  <button
                    onClick={sendMessage}
                    disabled={!message.trim() || loading}
                    className="bg-indigo-600 text-white p-3 rounded-full hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                  >
                    {loading ? (
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <Send className="w-5 h-5" />
                    )}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <MessageCircle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-xl font-medium text-gray-600 mb-2">Select or Create a Conversation</h3>
                <p className="text-gray-500">Choose an existing conversation or create a new one to get started</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default App;
