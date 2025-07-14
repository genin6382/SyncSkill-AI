"use client"

import { useState, useEffect } from "react"
import axios from "axios"
import { Upload, Send, FileText, CheckCircle, AlertCircle, User, Bot, MessageCircle } from "lucide-react"
import "./Home.css"

// Function to format AI response text
const formatAIResponse = (text) => {
  if (!text) return text

  // Convert **text** to proper headings
  let formatted = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")

  // Convert numbered lists and bullet points
  formatted = formatted
    .split("\n")
    .map((line) => {
      // Handle numbered lists (1. 2. 3. etc.)
      if (/^\d+\.\s/.test(line)) {
        return `<div class="numbered-item">${line}</div>`
      }
      // Handle bullet points (* text)
      if (/^\*\s/.test(line)) {
        return `<div class="bullet-item">• ${line.substring(2)}</div>`
      }
      // Regular paragraphs
      if (line.trim()) {
        return `<div class="paragraph">${line}</div>`
      }
      return "<br/>"
    })
    .join("")

  return formatted
}

function Home() {
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState("")
  const [query, setQuery] = useState("")
  const [chatHistory, setChatHistory] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)

  // Load chat history on component mount
  useEffect(() => {
    loadChatHistory()
  }, [])

  const loadChatHistory = async () => {
    try {
      setIsLoadingHistory(true)
      const response = await axios.get("http://localhost:5000/api/conversations", {
        withCredentials: true,
      })

      if (response.status === 200) {
        const conversations = response.data.flatMap((conv) => [
          {
            type: "user",
            message: conv.question,
            timestamp: new Date(conv.timestamp),
            id: conv.id,
          },
          {
            type: "ai",
            message: conv.answer,
            timestamp: new Date(conv.timestamp),
            id: conv.id,
          },
        ])

        setChatHistory(conversations)
      }
    } catch (error) {
      console.error("Failed to load chat history:", error)
      // Don't show error to user for history loading
    } finally {
      setIsLoadingHistory(false)
    }
  }

  const saveChatHistory = async (question, answer) => {
    try {
      await axios.post(
        "http://localhost:5000/api/1/conversations",
        {
          question: question,
          answer: answer,
        },
        {
          withCredentials: true,
        },
      )
    } catch (error) {
      console.error("Failed to save chat history:", error)
      // Don't interrupt user experience for save failures
    }
  }

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      const maxSize = 1024 * 1024 // 1MB
      if (selectedFile.size > maxSize) {
        setStatus(`File size (${(selectedFile.size / 1024 / 1024).toFixed(2)}MB) exceeds 1MB limit.`)
        setFile(null)
        e.target.value = ""
        return
      }
      setStatus("")
      setFile(selectedFile)
    }
  }

  const handleUpload = async () => {
    if (!file) {
      setStatus("Please select a file.")
      return
    }

    const formData = new FormData()
    formData.append("resume", file)

    try {
      setStatus("Uploading...")
      setIsLoading(true)
      const response = await axios.post("http://localhost:5000/api/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        withCredentials: true,
      })
      await getExtractedText()
    } catch (error) {
      console.error(error)
      if (error.response?.status === 400 && error.response?.data?.error?.includes("user_id")) {
        setStatus("Please log in first to upload a resume.")
      } else {
        setStatus("Upload failed: " + (error.response?.data?.error || error.message))
        if (error.response?.status === 413) {
          setStatus("File size exceeds 1MB limit. Please choose a smaller file.")
        }
      }
    } finally {
      setIsLoading(false)
    }
  }

  const getExtractedText = async () => {
    try {
      const res = await axios.get("http://localhost:5000/api/get-processed-text", {
        withCredentials: true,
      })
      if (res.status === 200) {
        setStatus("Successfully uploaded your file!")
      } else {
        setStatus("Failed to upload your file. Please try again.")
      }
    } catch (error) {
      console.error("Failed to get extracted text:", error)
      setStatus("Failed to retrieve extracted text.")
    }
  }

  const handleQuerySubmit = async () => {
    if (!query.trim()) {
      setStatus("Please enter a query.")
      return
    }

    const userMessage = query.trim()
    setStatus("Processing query...")
    setIsLoading(true)

    // Add user message to chat history immediately
    const userChatItem = {
      type: "user",
      message: userMessage,
      timestamp: new Date(),
    }

    setChatHistory((prev) => [...prev, userChatItem])
    setQuery("") // Clear input immediately

    try {
      const res = await axios.post(
        "http://localhost:5000/api/job-query",
        {
          query: userMessage,
        },
        {
          withCredentials: true,
        },
      )

      if (res.data?.success) {
        const aiResponse = res.data.response
        setStatus("Query processed successfully.")

        // Add AI response to chat history
        const aiChatItem = {
          type: "ai",
          message: aiResponse,
          timestamp: new Date(),
        }

        setChatHistory((prev) => [...prev, aiChatItem])

        // Save to database
        await saveChatHistory(userMessage, aiResponse)
      } else {
        setStatus("Query failed: " + (res.data?.error || "Unknown error"))
      }
    } catch (error) {
      console.error("Query failed:", error)
      setStatus("Query failed: " + (error.response?.data?.error || error.message))
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleQuerySubmit()
    }
  }

  return (
    <div className="home-container">
      {/* Header */}
      <div className="header">
        <div className="header-content">
          <h1 className="header-title">Resume AI Assistant</h1>
          <p className="header-subtitle">Upload your resume and get personalized job insights</p>
        </div>
      </div>

      <div className="main-content">
        {/* Upload Sidebar */}
        <div className="upload-sidebar">
          <div className="upload-card">
            <div className="upload-header">
              <Upload className="upload-icon" />
              <h2 className="upload-title">Upload Resume</h2>
            </div>

            {/* File Upload Area */}
            <div className="file-upload-area">
              <input
                type="file"
                accept=".pdf,.doc,.docx"
                onChange={handleFileChange}
                className="file-input"
                id="file-upload"
              />
              <label htmlFor="file-upload" className="file-label">
                <FileText className="file-icon" />
                <p className="file-text">Click to select your resume</p>
                <p className="file-subtext">PDF, DOC, DOCX (Max 1MB)</p>
              </label>
            </div>

            {/* File Info */}
            {file && (
              <div className="file-info">
                <div className="file-info-content">
                  <div className="file-details">
                    <p className="file-name">{file.name}</p>
                    <p className="file-size">{(file.size / 1024 / 1024).toFixed(2)}MB</p>
                  </div>
                  <div className="file-status">
                    {file.size > 1024 * 1024 ? (
                      <AlertCircle className="status-icon error" />
                    ) : (
                      <CheckCircle className="status-icon success" />
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Upload Button */}
            <button onClick={handleUpload} disabled={!file || isLoading} className="upload-button">
              {isLoading ? <div className="spinner"></div> : <Upload className="button-icon" />}
              {isLoading ? "Uploading..." : "Upload Resume"}
            </button>

            {/* Status */}
            {status && (
              <div
                className={`status-message ${
                  status.includes("Successfully")
                    ? "success"
                    : status.includes("failed") || status.includes("Failed") || status.includes("exceeds")
                      ? "error"
                      : "info"
                }`}
              >
                <p className="status-text">{status}</p>
              </div>
            )}
          </div>
        </div>

        {/* Chat Section - Centered and Main Focus */}
        <div className="chat-section">
          <div className="chat-card">
            <div className="chat-header">
              <MessageCircle className="chat-icon" />
              <h2 className="chat-title">AI Chat Assistant</h2>
            </div>

            {/* Chat History */}
            <div className="chat-history">
              {isLoadingHistory ? (
                <div className="loading-history">
                  <div className="spinner large"></div>
                  <p>Loading chat history...</p>
                </div>
              ) : chatHistory.length === 0 ? (
                <div className="empty-chat">
                  <Bot className="empty-icon" />
                  <p className="empty-title">Welcome to your AI Assistant!</p>
                  <p className="empty-subtitle">Ask me about job opportunities, skills, or career advice!</p>
                </div>
              ) : (
                chatHistory.map((chat, index) => (
                  <div key={index} className={`chat-message ${chat.type}`}>
                    <div className={`message-bubble ${chat.type}`}>
                      <div className="message-content">
                        {chat.type === "ai" && <Bot className="message-icon ai" />}
                        {chat.type === "user" && <User className="message-icon user" />}
                        <div className="message-text">
                          <div
                            className="message-body"
                            dangerouslySetInnerHTML={{
                              __html: chat.type === "ai" ? formatAIResponse(chat.message) : chat.message,
                            }}
                          />
                          <p className="message-time">{chat.timestamp.toLocaleTimeString()}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}

              {/* Loading indicator */}
              {isLoading && (
                <div className="chat-message ai">
                  <div className="message-bubble ai">
                    <div className="message-content">
                      <Bot className="message-icon ai" />
                      <div className="typing-indicator">
                        <div className="dot"></div>
                        <div className="dot"></div>
                        <div className="dot"></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Query Input */}
            <div className="query-input">
              <input
                type="text"
                placeholder="Ask about job roles, skills, or career advice..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                className="query-field"
                disabled={isLoading}
              />
              <button onClick={handleQuerySubmit} disabled={!query.trim() || isLoading} className="send-button">
                <Send className="send-icon" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Home
