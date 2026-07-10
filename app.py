import streamlit as st
import os
from datetime import datetime
import json
from pathlib import Path

# Import required libraries
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate

# Page configuration
st.set_page_config(
    page_title="📚 PDF Notes Taker",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a polished notes app UI
st.markdown("""
<style>
    /* Main container */
    .main {
        background-color: #f8f9fa;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #ffffff;
    }
    
    /* Chat messages */
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    
    .chat-message.user {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    
    .chat-message.assistant {
        background-color: #f5f5f5;
        border-left: 4px solid #4caf50;
    }
    
    /* Note cards */
    .note-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #1a237e;
    }
    
    /* Success/Info boxes */
    .stAlert {
        border-radius: 0.5rem;
    }
    
    /* Metrics */
    .metric-card {
        background-color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    /* Button styling */
    .stButton>button {
        border-radius: 0.5rem;
        font-weight: 500;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: white;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = None
if 'conversation' not in st.session_state:
    st.session_state.conversation = None
if 'notes' not in st.session_state:
    st.session_state.notes = []
if 'pdf_processed' not in st.session_state:
    st.session_state.pdf_processed = False
if 'pdf_name' not in st.session_state:
    st.session_state.pdf_name = ""

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF using pdfplumber"""
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def process_pdf(pdf_file):
    """Process PDF and create vector store"""
    with st.spinner("📖 Reading PDF..."):
        # Extract text
        raw_text = extract_text_from_pdf(pdf_file)
        
        if not raw_text.strip():
            st.error("❌ Could not extract text from PDF. The PDF might be scanned or empty.")
            return False
        
        st.success(f"✅ Extracted {len(raw_text)} characters from PDF")
    
    with st.spinner("✂️ Splitting text into chunks..."):
        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        chunks = text_splitter.split_text(raw_text)
        st.success(f"✅ Created {len(chunks)} text chunks")
    
    with st.spinner("🔢 Creating embeddings..."):
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=os.environ.get("GEMINI_API_KEY", "")
        )
        
        # Create vector store
        vectorstore = FAISS.from_texts(chunks, embeddings)
        st.session_state.vectorstore = vectorstore
        st.success("✅ Vector store created successfully!")
    
    return True

def setup_conversation_chain():
    """Setup the conversational chain"""
    if st.session_state.vectorstore is None:
        return None
    
    # Get Gemini API token
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    
    if not gemini_api_key:
        st.error("⚠️ Please set GEMINI_API_KEY in your environment")
        return None
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro",
        google_api_key=gemini_api_key,
        temperature=0.7
    )
    
    # Create memory
    memory = ConversationBufferMemory(
        memory_key='chat_history',
        return_messages=True,
        output_key='answer'
    )
    
    # Create custom prompt
    prompt_template = """You are a helpful AI assistant analyzing a PDF document. 
    Use the following context to answer the question. If you don't know the answer, say so.
    
    Context: {context}
    
    Question: {question}
    
    Answer:"""
    
    PROMPT = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )
    
    # Create conversation chain
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=st.session_state.vectorstore.as_retriever(search_kwargs={"k": 3}),
        memory=memory,
        combine_docs_chain_kwargs={"prompt": PROMPT},
        return_source_documents=True
    )
    
    return conversation_chain

def save_note(question, answer):
    """Save a note to session state"""
    note = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "question": question,
        "answer": answer
    }
    st.session_state.notes.append(note)

def export_notes():
    """Export notes as JSON"""
    notes_data = {
        "pdf_name": st.session_state.pdf_name,
        "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes": st.session_state.notes
    }
    return json.dumps(notes_data, indent=2)

# Main app layout
col1, col2 = st.columns([3, 1])

with col1:
    st.title("📚 PDF Notes Taker & RAG Chatbot")
    st.markdown("Upload a PDF, ask questions, and take notes!")

with col2:
    if st.session_state.pdf_processed:
        st.metric("📄 PDF Status", "Loaded ✅")
        st.metric("💬 Messages", len(st.session_state.messages))
        st.metric("📝 Notes", len(st.session_state.notes))

# Sidebar
with st.sidebar:
    st.header("📁 Upload PDF")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload a PDF document to analyze"
    )
    
    if uploaded_file is not None:
        st.session_state.pdf_name = uploaded_file.name
        
        if st.button("🚀 Process PDF", type="primary", use_container_width=True):
            success = process_pdf(uploaded_file)
            if success:
                st.session_state.pdf_processed = True
                st.session_state.conversation = setup_conversation_chain()
                st.rerun()
    
    st.divider()
    
    # PDF Info
    if st.session_state.pdf_processed:
        st.success(f"📄 **{st.session_state.pdf_name}**")
        
        st.divider()
        
        # Notes section
        st.header("📝 Saved Notes")
        
        if st.session_state.notes:
            if st.button("💾 Export Notes", use_container_width=True):
                notes_json = export_notes()
                st.download_button(
                    label="⬇️ Download JSON",
                    data=notes_json,
                    file_name=f"notes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            if st.button("🗑️ Clear Notes", use_container_width=True):
                st.session_state.notes = []
                st.rerun()
            
            st.divider()
            
            for i, note in enumerate(reversed(st.session_state.notes)):
                with st.expander(f"Note {len(st.session_state.notes) - i}: {note['question'][:50]}..."):
                    st.caption(f"🕐 {note['timestamp']}")
                    st.markdown(f"**Q:** {note['question']}")
                    st.markdown(f"**A:** {note['answer']}")
        else:
            st.info("No notes saved yet")
    
    st.divider()
    
    # Clear conversation button
    if st.button("🔄 Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        if st.session_state.conversation:
            st.session_state.conversation.memory.clear()
        st.rerun()
    
    # Reset app button
    if st.button("♻️ Reset App", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Main content area
if not st.session_state.pdf_processed:
    # Welcome screen
    st.info("👋 Welcome! Please upload a PDF file from the sidebar to get started.")
    
    st.markdown("""
    ### How to use:
    1. 📤 Upload a PDF file from the sidebar
    2. 🚀 Click "Process PDF" to analyze the document
    3. 💬 Ask questions about the PDF in the chat
    4. 📝 Save important answers as notes
    5. 💾 Export your notes when done
    """)
    
    st.markdown("""
    ### Features:
    - 🤖 AI-powered question answering using RAG (Retrieval Augmented Generation)
    - 📊 Intelligent text chunking and vector embeddings
    - 💾 Save and export notes
    - 🔍 Context-aware responses
    - 📱 Clean, modern UI
    """)

else:
    # Chat interface
    st.markdown("### 💬 Chat with your PDF")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and "note_id" not in message:
                if st.button(f"📝 Save as Note", key=f"save_{len(st.session_state.messages)}_{message['content'][:20]}"):
                    # Find the corresponding question
                    idx = st.session_state.messages.index(message)
                    if idx > 0:
                        question = st.session_state.messages[idx-1]["content"]
                        save_note(question, message["content"])
                        st.success("Note saved!")
                        st.rerun()
    
    # Chat input
    if prompt := st.chat_input("Ask a question about your PDF..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                if st.session_state.conversation:
                    response = st.session_state.conversation({"question": prompt})
                    answer = response['answer']
                    
                    st.markdown(answer)
                    
                    # Add assistant message
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    st.error("Conversation chain not initialized. Please process the PDF first.")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p>Built with ❤️ using Streamlit • Powered by Google Gemini 🌟</p>
</div>
""", unsafe_allow_html=True)
