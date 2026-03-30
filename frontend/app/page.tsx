"use client";

import { useState, useEffect, useRef } from "react";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Session {
  id: number;
  title: string;
}

interface Source {
  filename: string;
  page: number;
  text_snippet: string;
}

interface Message {
  id: number;
  role: string;
  content: string;
  sources: Source[];
}

export default function Home() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchSessions();
  }, []);

  useEffect(() => {
    if (activeSession !== null) {
      fetchMessages(activeSession);
    } else {
      setMessages([]);
    }
  }, [activeSession]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_URL}/sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch (e) {
      console.error("Failed to fetch sessions");
    }
  };

  const fetchMessages = async (sessionId: number) => {
    try {
      const res = await fetch(`${API_URL}/sessions/${sessionId}/messages`);
      if (res.ok) {
        setMessages(await res.json());
      }
    } catch (e) {
      console.error("Failed to fetch messages");
    }
  };

  const createNewSession = async () => {
    try {
      const res = await fetch(`${API_URL}/sessions`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setSessions([data, ...sessions]);
        setActiveSession(data.id);
      }
    } catch (e) {
      console.error("Failed to create session");
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    
    let currentSessionId = activeSession;
    if (currentSessionId === null) {
      try {
        const res = await fetch(`${API_URL}/sessions`, { method: "POST" });
        if (res.ok) {
          const data = await res.json();
          setSessions([data, ...sessions]);
          currentSessionId = data.id;
          setActiveSession(data.id);
        }
      } catch (e) {
        return;
      }
    }

    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content: input,
      sources: []
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionId,
          message: userMessage.content
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        const asstMessage: Message = {
          id: Date.now() + 1,
          role: "assistant",
          content: data.response,
          sources: data.sources || []
        };
        setMessages(prev => [...prev, asstMessage]);
        fetchSessions(); // refresh titles
      }
    } catch (e) {
      console.error("Failed to send message", e);
      // fallback message on failure
      setMessages(prev => [...prev, {
        id: Date.now() + 2,
        role: "assistant",
        content: "Error connecting to the backend intelligence. Check if API is running.",
        sources: []
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className={styles.container}>
      <div className={styles.sidebar}>
        <div className={styles.sidebarTitle}>
          <span>AI</span> Knowledge Platform
        </div>
        <button className={styles.newChatBtn} onClick={createNewSession}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          New Chat
        </button>
        <div className={styles.sessionList}>
          {sessions.map(s => (
            <button 
              key={s.id} 
              className={`${styles.sessionItem} ${activeSession === s.id ? styles.active : ''}`}
              onClick={() => setActiveSession(s.id)}
            >
              {s.title}
            </button>
          ))}
        </div>
      </div>
      
      <div className={styles.chatArea}>
        {messages.length === 0 && !loading ? (
          <div className={styles.emptyState}>
            <h2>How can I help you today?</h2>
            <p>Select a document or just ask a question.</p>
          </div>
        ) : (
          <div className={styles.messages}>
            {messages.map(m => (
              <div key={m.id} className={`${styles.messageRow} ${styles[m.role]}`}>
                <div className={styles.bubble}>
                  <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                  {m.sources && m.sources.length > 0 && (
                    <div className={styles.sourcesList}>
                      {m.sources.map((src, i) => (
                        <div key={i} className={styles.sourceCard}>
                          <span>{src.filename} (Pg {src.page})</span>
                          <div className={styles.sourceSnippet}>{src.text_snippet}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className={`${styles.messageRow} ${styles.assistant}`}>
                <div className={styles.bubble} style={{ opacity: 0.7 }}>Thinking...</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
        
        <div className={styles.inputArea}>
          <div className={styles.inputBox}>
            <input 
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                  }
              }}
              placeholder="Ask anything..."
              disabled={loading}
            />
            <button 
              className={styles.sendBtn} 
              onClick={sendMessage}
              disabled={loading || !input.trim()}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
