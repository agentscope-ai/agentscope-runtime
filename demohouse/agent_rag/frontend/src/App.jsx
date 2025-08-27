import React, { useState, useEffect, useRef } from 'react';
import { MessageCircle, User, Send, Plus, LogOut, Menu, X, Bot, Paperclip, Upload, Trash2, FileText, Folder, Trash } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';

const App = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [currentUser, setCurrentUser] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [message, setMessage] = useState('');
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // --- NEW STATE FOR AGENTIC RAG FEATURES ---
  const [knowledgeBaseFiles, setKnowledgeBaseFiles] = useState([]); // [{id, name, type, status}]
  const [isUploading, setIsUploading] = useState(false);
  const [messageFiles, setMessageFiles] = useState([]); // Files attached to the current message
  const fileInputRef = useRef(null); // Ref for the hidden file input for message attachments
  const kbFileInputRef = useRef(null); // Ref for the hidden file input for KB uploads

  const messagesEndRef = useRef(null);

  // API base URL
  const API_BASE = 'http://localhost:5100/api'; // Ensure this points to your backend

  // Auto scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages]);

  // Component to render message content with markdown support
  const MessageContent = ({ message, isUser }) => {
    if (isUser) {
      // For user messages, render as plain text
      return <p className="text-sm">{message.text}</p>;
    }

    // For assistant messages, render as markdown
    return (
      <div className="text-sm prose prose-sm max-w-none">
        <ReactMarkdown
          components={{
            code({ node, inline, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              return !inline && match ? (
                <SyntaxHighlighter
                  style={tomorrow}
                  language={match[1]}
                  PreTag="div"
                  className="!mt-2 !mb-2 !text-xs"
                  {...props}
                >
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              ) : (
                <code className="bg-gray-100 px-1 py-0.5 rounded text-xs" {...props}>
                  {children}
                </code>
              );
            },
            p: ({ children }) => (
              <p className="mb-2 last:mb-0">{children}</p>
            ),
            ul: ({ children }) => (
              <ul className="list-disc ml-4 mb-2">{children}</ul>
            ),
            ol: ({ children }) => (
              <ol className="list-decimal ml-4 mb-2">{children}</ol>
            ),
            li: ({ children }) => (
              <li className="mb-1">{children}</li>
            ),
            blockquote: ({ children }) => (
              <blockquote className="border-l-4 border-gray-300 pl-4 italic mb-2">
                {children}
              </blockquote>
            ),
            h1: ({ children }) => (
              <h1 className="text-lg font-bold mb-2">{children}</h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-base font-bold mb-2">{children}</h2>
            ),
            h3: ({ children }) => (
              <h3 className="text-sm font-bold mb-2">{children}</h3>
            ),
            a: ({ children, href }) => (
              <a href={href} className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            ),
            table: ({ children }) => (
              <table className="border-collapse border border-gray-300 mb-2 text-xs">
                {children}
              </table>
            ),
            th: ({ children }) => (
              <th className="border border-gray-300 px-2 py-1 bg-gray-100 font-medium">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="border border-gray-300 px-2 py-1">{children}</td>
            ),
          }}
        >
          {message.text}
        </ReactMarkdown>
      </div>
    );
  };

  // --- NEW: Fetch Knowledge Base Files ---
  const fetchKnowledgeBase = async (userId) => {
    if (!userId) {
      console.log('fetchKnowledgeBase: no userId provided');
      return;
    }
    
    console.log(`Fetching knowledge base for user ${userId}`);
    
    try {
      const response = await fetch(`${API_BASE}/knowledge-files`, {
        credentials: 'include',
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log(`Fetched ${data.length} knowledge base files`);
        
        // Transform the data to match the expected format in the UI
        const transformedData = data.map(file => ({
          id: file.id,
          name: file.filename,
          type: 'file', // All are files for now
          uploaded_at: file.uploaded_at
        }));
        
        setKnowledgeBaseFiles(transformedData);
      } else {
        const errorText = await response.text();
        let errorData;
        try {
          errorData = JSON.parse(errorText);
        } catch {
          errorData = { error: errorText || response.statusText };
        }
        
        console.error('Failed to fetch knowledge base:', errorData.error);
        
        // Only show error if it's not an authentication issue
        if (response.status !== 401 && response.status !== 403) {
          console.warn(`Knowledge base fetch failed: ${errorData.error}`);
        }
        
        // Clear list on error
        setKnowledgeBaseFiles([]);
      }
    } catch (error) {
      console.error('Error fetching knowledge base:', error);
      
      // Only show error for network issues, not auth redirects
      if (error.name !== 'TypeError' || !error.message.includes('Failed to fetch')) {
        console.warn(`Network error fetching knowledge base: ${error.message}`);
      }
      
      // Clear list on network error
      setKnowledgeBaseFiles([]);
    }
  };

  // Fetch user conversations
  const fetchConversations = async (userId) => {
    try {
      const response = await fetch(`${API_BASE}/conversations`, { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        setConversations(data);
        if (data.length > 0 && !activeConversation) {
          // Load the first conversation
          loadConversation(data[0].id);
        }
      }
    } catch (error) {
      console.error('Error fetching conversations:', error);
    }
  };

  // Load conversation details
  const loadConversation = async (conversationId) => {
    try {
      const response = await fetch(`${API_BASE}/conversations/${conversationId}`, { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        setActiveConversation(data);
      }
    } catch (error) {
      console.error('Error loading conversation:', error);
    }
  };

  // Login function
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ username, password }),
      });
      if (response.ok) {
        const resp = await response.json();
        // /api/login returns { message, user: { id, username, name } }
        const userData = resp.user || resp;
        setCurrentUser(userData);
        setIsLoggedIn(true);
        await fetchConversations(userData.id);
        // --- NEW: Fetch knowledge base after login ---
        await fetchKnowledgeBase(userData.id);
      } else {
        const errorData = await response.json();
        alert(errorData.error || 'Login failed');
      }
    } catch (error) {
      console.error('Login error:', error);
      alert('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Logout function
  const handleLogout = () => {
    setIsLoggedIn(false);
    setCurrentUser(null);
    setUsername('');
    setPassword('');
    setConversations([]);
    setActiveConversation(null);
    setIsMenuOpen(false);
    // --- NEW: Reset knowledge base state on logout ---
    setKnowledgeBaseFiles([]);
    setMessageFiles([]);
  };

  // Create new conversation
  const createNewConversation = async () => {
    if (!currentUser) return;
    setLoading(true);
    try {
      // Use server-side current_user via protected endpoint
      const response = await fetch(`${API_BASE}/conversations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ title: 'New Conversation' }),
      });
      if (response.ok) {
        const newConversation = await response.json();
        setConversations(prev => [newConversation, ...prev]);
        await loadConversation(newConversation.id);
      }
    } catch (error) {
      console.error('Error creating conversation:', error);
    } finally {
      setLoading(false);
      setIsMenuOpen(false);
    }
  };

  // Delete conversation
  const deleteConversation = async (conversationId, e) => {
    e.stopPropagation(); // Prevent conversation selection when clicking delete
    
    if (!window.confirm('Are you sure you want to delete this conversation? This action cannot be undone.')) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/conversations/${conversationId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      
      if (response.ok) {
        // Remove conversation from the list
        setConversations(prev => prev.filter(conv => conv.id !== conversationId));
        
        // If the deleted conversation was active, clear it or select another one
        if (activeConversation?.id === conversationId) {
          const remainingConversations = conversations.filter(conv => conv.id !== conversationId);
          if (remainingConversations.length > 0) {
            await loadConversation(remainingConversations[0].id);
          } else {
            setActiveConversation(null);
          }
        }
      } else {
        const errorData = await response.json();
        alert(`Failed to delete conversation: ${errorData.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
      alert('Network error while deleting conversation. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Send message
  const sendMessage = async () => {
    if ((!message.trim() && messageFiles.length === 0) || !activeConversation) return;
    setLoading(true);
    
    // Check if user wants to save to Notion
    const notionKeywords = ['save to notion', 'export to notion', 'save this to notion', 'notion save', 'save in notion'];
    const shouldSaveToNotion = notionKeywords.some(keyword => 
      message.toLowerCase().includes(keyword.toLowerCase())
    );
    
    try {
        // Prepare data for sending
        let messagePayload = { text: message, sender: 'user' };
        let formData = null;

        if (messageFiles.length > 0) {
             // If files are attached, use FormData
             formData = new FormData();
             formData.append('text', message); // Add text content
             formData.append('sender', 'user');
             messageFiles.forEach((file, index) => {
                 formData.append(`files`, file); // Append files with key 'files'
             });
        }

        // Send user message
        const userMessageResponse = await fetch(`${API_BASE}/conversations/${activeConversation.id}/messages`, {
            method: 'POST',
            headers: formData ? {} : { // Don't set Content-Type for FormData
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: formData ? formData : JSON.stringify(messagePayload),
        });

        if (userMessageResponse.ok) {
            const userMessage = await userMessageResponse.json();
            // Update UI with user message
            const updatedConversation = {
                ...activeConversation,
                messages: [...activeConversation.messages, userMessage],
                title: activeConversation.messages.length === 1 ? (message.slice(0, 20) + (message.length > 20 ? '...' : '')) || 'New Conversation' : activeConversation.title
            };
            setActiveConversation(updatedConversation);
            setMessage('');
            setMessageFiles([]); // Clear attached files after sending
            
            // If user requested Notion save, export the last AI message
            if (shouldSaveToNotion) {
              await handleNotionExport();
            }
            
            // Fetch updated conversation to get AI response
            await loadConversation(activeConversation.id);
        }
    } catch (error) {
        console.error('Error sending message:', error);
    } finally {
        setLoading(false);
    }
};


  // Format timestamp - synchronized with computer's local time
  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInMs = now - date;
    const diffInHours = diffInMs / (1000 * 60 * 60);
    
    // If the message is from today, show time only
    if (diffInHours < 24 && date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true // Use 12-hour format with AM/PM
      });
    }
    // If the message is from yesterday, show "Yesterday" + time
    else if (diffInHours < 48) {
      const yesterday = new Date(now);
      yesterday.setDate(yesterday.getDate() - 1);
      if (date.toDateString() === yesterday.toDateString()) {
        return `Yesterday ${date.toLocaleTimeString(undefined, {
          hour: '2-digit',
          minute: '2-digit',
          hour12: true
        })}`;
      }
    }
    
    // For older messages, show date + time
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  };

  // --- NEW: Handle File Upload for Knowledge Base---
  const handleKBFileUpload = async (files) => {
    if (!currentUser || !files || files.length === 0) {
      console.log('Upload cancelled: missing user or files');
      return;
    }
    
    console.log(`Starting upload of ${files.length} file(s)`);
    setIsUploading(true);
    
    let successCount = 0;
    let errorCount = 0;
    let lastError = '';
    const uploadedFiles = [];

    try {
      // Upload files one by one since backend handles single files
      for (let i = 0; i < files.length; i++) {
        const currentFile = files[i];
        console.log(`Uploading file ${i + 1}/${files.length}: ${currentFile.name}`);
        
        const formData = new FormData();
        formData.append('file', currentFile); // Backend expects 'file' field (singular)
        
        try {
          const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            credentials: 'include',
            body: formData,
          });

          if (response.ok) {
            const result = await response.json();
            console.log(`KB Upload successful for ${currentFile.name}:`, result);
            successCount++;
            uploadedFiles.push(currentFile.name);
            
            // Refresh knowledge base after each successful upload to show progress
            try {
              await fetchKnowledgeBase(currentUser.id);
            } catch (fetchError) {
              console.warn('Failed to refresh knowledge base after upload:', fetchError);
            }
          } else {
            const errorText = await response.text();
            let errorData;
            try {
              errorData = JSON.parse(errorText);
            } catch {
              errorData = { error: errorText || response.statusText };
            }
            
            console.error(`KB Upload failed for ${currentFile.name}:`, errorData.error);
            lastError = errorData.error || `HTTP ${response.status}: ${response.statusText}`;
            errorCount++;
          }
        } catch (error) {
          console.error(`KB Upload error for ${currentFile.name}:`, error);
          lastError = error.message || 'Network error';
          errorCount++;
        }
      }
      
      // Show detailed results to user
      if (successCount > 0 && errorCount === 0) {
        console.log('All uploads completed successfully');
        alert(`✅ Successfully uploaded ${successCount} file(s) to knowledge base:\n${uploadedFiles.join(', ')}`);
      } else if (successCount > 0 && errorCount > 0) {
        console.log(`Partial success: ${successCount} succeeded, ${errorCount} failed`);
        alert(`⚠️ Uploaded ${successCount} file(s) successfully, but ${errorCount} failed.\n\nSuccessful: ${uploadedFiles.join(', ')}\nLast error: ${lastError}`);
      } else if (errorCount > 0) {
        console.log('All uploads failed');
        alert(`❌ Failed to upload files. Error: ${lastError}`);
      }
      
      // Clear file input
      if (kbFileInputRef.current) {
        kbFileInputRef.current.value = '';
      }
      
    } catch (error) {
      console.error('KB Upload general error:', error);
      alert(`❌ Network error during upload: ${error.message}. Please check your connection and try again.`);
    } finally {
      console.log('Upload process finished, clearing loading state');
      setIsUploading(false);
      
      // Final refresh of knowledge base to ensure UI is up to date
      try {
        await fetchKnowledgeBase(currentUser.id);
      } catch (fetchError) {
        console.warn('Failed final knowledge base refresh:', fetchError);
      }
    }
  };

  // --- NEW: Handle File Delete from Knowledge Base ---
  const handleDeleteFile = async (fileId) => {
    if (!fileId || !currentUser) {
      console.log('Delete cancelled: missing file ID or user');
      return;
    }
    
    // Find the file info for better user feedback
    const fileToDelete = knowledgeBaseFiles.find(f => f.id === fileId);
    const fileName = fileToDelete ? fileToDelete.name : `File ID ${fileId}`;
    
    // Basic confirmation with file name
    if (!window.confirm(`Are you sure you want to delete "${fileName}" from the knowledge base?\n\nThis action cannot be undone.`)) {
      console.log('Delete cancelled by user');
      return;
    }

    console.log(`Starting deletion of file: ${fileName} (ID: ${fileId})`);
    
    // Set deleting state to prevent multiple deletions and show progress
    const fileIndex = knowledgeBaseFiles.findIndex(f => f.id === fileId);
    if (fileIndex !== -1) {
      const updatedFiles = [...knowledgeBaseFiles];
      updatedFiles[fileIndex] = { ...updatedFiles[fileIndex], deleting: true };
      setKnowledgeBaseFiles(updatedFiles);
    }

    try {
      const response = await fetch(`${API_BASE}/knowledge-files/${fileId}`, {
        method: 'DELETE',
        credentials: 'include',
      });

      if (response.ok) {
         console.log(`File "${fileName}" deleted successfully from server`);
         alert(`✅ Successfully deleted "${fileName}" from knowledge base.`);
         
         // Immediately refresh knowledge base list
         await fetchKnowledgeBase(currentUser.id);
      } else {
         const errorText = await response.text();
         let errorData;
         try {
           errorData = JSON.parse(errorText);
         } catch {
           errorData = { error: errorText || response.statusText };
         }
         
         const errorMessage = errorData.error || `HTTP ${response.status}: ${response.statusText}`;
         console.error(`Delete failed for "${fileName}":`, errorMessage);
         alert(`❌ Failed to delete "${fileName}": ${errorMessage}`);
         
         // Reset deleting state on error by refreshing the list
         await fetchKnowledgeBase(currentUser.id);
      }
    } catch (error) {
      console.error(`Network error deleting "${fileName}":`, error);
      alert(`❌ Network error while deleting "${fileName}": ${error.message}. Please check your connection and try again.`);
      
      // Reset deleting state on error by refreshing the list
      try {
        await fetchKnowledgeBase(currentUser.id);
      } catch (fetchError) {
        console.warn('Failed to refresh knowledge base after delete error:', fetchError);
      }
    }
  };

  // --- NEW: Handle Notion Export of Last AI Message ---
  const handleNotionExport = async () => {
    if (!activeConversation || activeConversation.messages.length === 0) {
      console.log("No messages to export");
      return;
    }
    
    // Find the last AI message
    const lastAiMessage = activeConversation.messages
      .slice()
      .reverse()
      .find(msg => msg.sender === 'ai');
    
    if (!lastAiMessage) {
      console.log("No AI messages found to export");
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE}/export/notion/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ 
          message_id: lastAiMessage.id,
          conversation_id: activeConversation.id 
        }),
      });

      if (response.ok) {
        const result = await response.json();
        console.log("Message exported to Notion:", result);
        // Show a brief success indicator (you could add a toast notification here)
      } else {
        const errorData = await response.json();
        console.error("Failed to export message:", errorData.error || response.statusText);
      }
    } catch (error) {
      console.error('Error exporting message to Notion:', error);
    }
  };

  // --- NEW: Handle File Attachment for Message ---
  const handleAttachFile = (files) => {
    if (files && files.length > 0) {
        const newFiles = Array.from(files);
        setMessageFiles(prevFiles => [...prevFiles, ...newFiles]);
        // Clear the input value to allow re-uploading the same file
        if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // --- NEW: Remove a specific file from message attachments ---
  const removeAttachedFile = (fileName) => {
    setMessageFiles(prevFiles => prevFiles.filter(file => file.name !== fileName));
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
              {loading ? 'Logging in...' : 'Login'}
            </button>
          </form>
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-2">Demo accounts:</p>
            <p className="text-xs text-gray-500">Username: testuser1, Password: testpass1</p>
            <p className="text-xs text-gray-500">Username: testuser2, Password: testpass2</p>
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
            <div className="absolute left-0 top-0 h-full w-80 bg-white shadow-xl lg:relative lg:shadow-none z-10 flex flex-col">
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
                    className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors group ${
                      activeConversation?.id === conversation.id ? 'bg-indigo-50 border-l-4 border-l-indigo-500' : ''
                    }`}
                  >
                    <div
                      onClick={() => {
                        loadConversation(conversation.id);
                        setIsMenuOpen(false);
                      }}
                      className="flex items-start space-x-3"
                    >
                      <MessageCircle className="w-5 h-5 text-gray-400 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-gray-900 truncate">{conversation.title}</h3>
                        <p className="text-sm text-gray-500 truncate">
                          {conversation.preview || 'New conversation'}
                        </p>
                      </div>
                      <button
                        onClick={(e) => deleteConversation(conversation.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-100 text-gray-400 hover:text-red-500 transition-all flex-shrink-0"
                        disabled={loading}
                        aria-label={`Delete conversation: ${conversation.title}`}
                      >
                        <Trash className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* --- NEW: Knowledge Base Section --- */}
              <div className="p-4 border-t border-gray-200 mt-4 flex flex-col">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-md font-semibold text-gray-800">Knowledge Base</h3>
                  <label className={`text-white text-xs px-2 py-1 rounded-lg transition-colors cursor-pointer flex items-center ${isUploading ? 'bg-gray-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'}`}>
                    {isUploading ? (
                      <>
                        <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin mr-1" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Upload className="w-3 h-3 mr-1" /> Upload
                      </>
                    )}
                    <input
                      type="file"
                      multiple
                      ref={kbFileInputRef}
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files && e.target.files.length > 0) {
                          console.log(`Selected ${e.target.files.length} file(s) for upload`);
                          handleKBFileUpload(e.target.files);
                        }
                      }}
                      disabled={isUploading}
                    />
                  </label>
                </div>
                <div className="flex-1 max-h-40 overflow-y-auto border border-gray-200 rounded-md bg-gray-50">
                  {knowledgeBaseFiles.length > 0 ? (
                    <ul className="divide-y divide-gray-200">
                      {knowledgeBaseFiles.map((file) => (
                        <li key={file.id} className="p-2 flex items-center justify-between text-sm">
                          <div className={`flex items-center truncate ${
                            file.deleting ? 'opacity-50' : ''
                          }`}>
                            {file.type === 'folder' ? (
                              <Folder className="w-4 h-4 text-gray-500 mr-2 flex-shrink-0" />
                            ) : (
                              <FileText className="w-4 h-4 text-gray-500 mr-2 flex-shrink-0" />
                            )}
                            <span className="truncate">
                              {file.name}
                              {file.deleting && (
                                <span className="ml-2 text-xs text-gray-500 italic">Deleting...</span>
                              )}
                            </span>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation(); // Prevent list item click
                              handleDeleteFile(file.id);
                            }}
                            className={`flex items-center flex-shrink-0 ml-2 transition-colors ${
                              file.deleting
                                ? 'text-gray-400 cursor-not-allowed'
                                : 'text-red-500 hover:text-red-700'
                            }`}
                            aria-label={`Delete ${file.name}`}
                            disabled={isUploading || file.deleting} // Prevent actions during upload or delete
                          >
                            {file.deleting ? (
                              <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-gray-500 text-center p-4 text-xs">
                      {isUploading ? 'Uploading files...' : 'No files uploaded.'}
                    </p>
                  )}
                </div>
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
              <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
                <h2 className="font-semibold text-gray-800 flex-1 truncate">{activeConversation.title}</h2>
              </div>
              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {activeConversation.messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-sm lg:max-w-4xl xl:max-w-5xl px-4 py-3 rounded-2xl ${
                        msg.sender === 'user'
                          ? 'bg-indigo-600 text-white rounded-br-md'
                          : 'bg-white text-gray-800 border border-gray-200 rounded-bl-md shadow-sm'
                      }`}
                    >
                      <MessageContent message={msg} isUser={msg.sender === 'user'} />
                      {/* --- NEW: Display attached files for user messages --- */}
                      {msg.sender === 'user' && msg.files && msg.files.length > 0 && (
                        <div className="mt-2 text-xs">
                          <p className="font-medium">Attached Files:</p>
                          <ul className="list-disc pl-4">
                            {msg.files.map((file, index) => (
                              <li key={index} className="truncate">{file.name || file.filename}</li> // Adjust based on backend response
                            ))}
                          </ul>
                        </div>
                      )}
                      <p className={`text-xs mt-1 ${msg.sender === 'user' ? 'text-indigo-100' : 'text-gray-500'}`}>
                        {formatTime(msg.created_at)}
                      </p>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
              {/* Input Area */}
              <div className="bg-white border-t border-gray-200 p-4">
                {/* --- NEW: Display attached files for the current message --- */}
                {messageFiles.length > 0 && (
                  <div className="mb-2 flex flex-wrap gap-1">
                    {messageFiles.map((file, index) => (
                      <div key={index} className="flex items-center bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded">
                        <Paperclip className="w-3 h-3 mr-1" />
                        <span className="truncate max-w-[100px]">{file.name}</span>
                        <button
                          type="button"
                          onClick={() => removeAttachedFile(file.name)}
                          className="ml-1 text-gray-500 hover:text-red-500"
                          aria-label={`Remove ${file.name}`}
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center space-x-3">
                  {/* --- NEW: Paperclip button for message attachment --- */}
                  <label className="p-2 rounded-full hover:bg-gray-100 transition-colors cursor-pointer">
                    <Paperclip className="w-5 h-5 text-gray-500" />
                    <input
                      type="file"
                      multiple
                      ref={fileInputRef}
                      className="hidden"
                      onChange={(e) => handleAttachFile(e.target.files)}
                    />
                  </label>
                  <input
                    type="text"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && !loading && sendMessage()}
                    disabled={loading}
                    className="flex-1 px-4 py-3 border border-gray-300 rounded-full focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all disabled:opacity-50"
                    placeholder="Type a message..."
                  />
                  <button
                    onClick={sendMessage}
                    disabled={(!message.trim() && messageFiles.length === 0) || loading}
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