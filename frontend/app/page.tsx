"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import styles from "./page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Dummy token matching our Auth backend bypass in `dev_secret` state.
const MOCK_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJzdWIiOiJ0ZXN0X3VzZXIifQ.dummy_signature";

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
  const [expandedSource, setExpandedSource] = useState<{msgId: number, idx: number} | null>(null);
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
      const res = await fetch(`${API_URL}/sessions`, {
        headers: { "Authorization": `Bearer ${MOCK_JWT}` }
      });
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
      const res = await fetch(`${API_URL}/sessions/${sessionId}/messages`, {
        headers: { "Authorization": `Bearer ${MOCK_JWT}` }
      });
      if (res.ok) {
        setMessages(await res.json());
      }
    } catch (e) {
      console.error("Failed to fetch messages");
    }
  };

  const createNewSession = async () => {
    try {
      const res = await fetch(`${API_URL}/sessions`, { 
        method: "POST",
        headers: { "Authorization": `Bearer ${MOCK_JWT}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSessions([data, ...sessions]);
        setActiveSession(data.id);
      }
    } catch (e) {
      console.error("Failed to create session");
    }
  };

  const deleteSession = async (e: React.MouseEvent, sessionId: number) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this chat?")) return;

    try {
      const res = await fetch(`${API_URL}/sessions/${sessionId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${MOCK_JWT}` }
      });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== sessionId));
        if (activeSession === sessionId) {
          setActiveSession(null);
        }
      }
    } catch (e) {
      console.error("Failed to delete session");
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    
    let currentSessionId = activeSession;
    if (currentSessionId === null) {
      try {
        const res = await fetch(`${API_URL}/sessions`, { 
          method: "POST",
          headers: { "Authorization": `Bearer ${MOCK_JWT}` }
        });
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
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${MOCK_JWT}`
        },
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
        <div style={{ marginTop: '10px' }}>
          <Link href="/admin">
            <button className={styles.newChatBtn} style={{ background: '#333' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px'}}><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
              Admin Board
            </button>
          </Link>
        </div>
        <div className={styles.sessionList}>
          {sessions.map(s => (
            <div 
              key={s.id} 
              className={`${styles.sessionItemContainer} ${activeSession === s.id ? styles.active : ''}`}
              onClick={() => setActiveSession(s.id)}
            >
              <span className={styles.sessionTitle}>{s.title}</span>
              <button 
                className={styles.deleteSessionBtn}
                onClick={(e) => deleteSession(e, s.id)}
                title="Delete chat"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
              </button>
            </div>
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
              <div key={m.id} className={`${styles.messageRow} ${styles[m.role]}`} data-testid="message-row">
                <div className={styles.bubble} data-testid="message-bubble">
                  <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>

                  {/* SQL Preview Component */}
                  {m.role === 'assistant' && (m.content.includes("SELECT") || m.content.includes("query_parquet")) && (
                    <div className={styles.sqlPreview} data-testid="sql-preview">
                        <div className={styles.sqlHeader}>SQL Tool Output</div>
                        <pre className={styles.sqlCode} data-testid="sql-code">
                            {m.content.toLowerCase().includes("select") ? "SELECT * FROM ... [Structured Result]" : "Structured query executed."}
                        </pre>
                    </div>
                  )}
                  {m.sources && m.sources.length > 0 && (
                    <div className={styles.sourcesList}>
                      {m.sources.map((src, i) => {
                        const isExpanded = expandedSource?.msgId === m.id && expandedSource?.idx === i;
                        return (
                          <div 
                            key={i} 
                            className={`${styles.sourceCard} ${isExpanded ? styles.expanded : ""}`}
                            onClick={() => setExpandedSource(isExpanded ? null : { msgId: m.id, idx: i })}
                          >
                            <div className={styles.sourceHeader}>
                              <span>{src.filename} (Pg {src.page})</span>
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: isExpanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}><path d="m6 9 6 6 6-6"></path></svg>
                            </div>
                            <div className={styles.sourceSnippet}>
                              {isExpanded ? src.text_snippet : (src.text_snippet.length > 100 ? src.text_snippet.slice(0, 100) + "..." : src.text_snippet)}
                            </div>
                          </div>
                        );
                      })}
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
