# Code Swarm: AI-Powered Programming Assistants

Welcome to **Code Swarm**, a suite of AI-powered agents designed to assist with programming tasks, maintain, and document Python and Lua codebases. With a sleek web interface, real-time logging, and powerful AI features, Code Swarm is the ultimate tool for managing and improving your codebase.

![logo](logo.png)

---

## 🚀 **Overview**

Code Swarm consists of:
1. A **set of specialized agents** for different coding tasks.
2. A **central controller** that manages all agents.
3. A **modern web interface** for monitoring and control.

These components work seamlessly together to help you automate repetitive tasks, track code changes, maintain documentation, and visualize dependencies.

---

## 🔥 **Quick Start**

### 1. **Clone the Repository**

First, clone the repository and navigate to the project folder:

```bash
git clone https://github.com/admica/code_swarm.git
cd code_swarm
```

### 2. **Install Dependencies**

Run the setup script to install all necessary dependencies:

```bash
python setup.py
```

### 3. **Start the Application**

Now, start the backend and frontend:

```bash
python run.py
```

### 4. **Open in Browser**

Open `http://localhost:3000` in your browser to access the application. The backend will run on port `8000`, and the frontend on `3000`.

---

### **Automatic Setup**
- The backend server starts on port `8000`.
- The frontend development server starts on port `3000`.
- Real-time WebSocket logging is enabled.
- All required services are initialized.

To stop the application, press `Ctrl+C` in the terminal where `run.py` is running.

---

## 🛠️ **Components**

### **Backend**

#### **Swarm Controller**

The **central server** that manages agents and offers various API endpoints, including:
- **RESTful API** for controlling agents.
- **WebSocket** for real-time logging.
- **LLM Integration** with features such as:
  - Request queueing.
  - Automatic retries.
  - Health monitoring.
  - Usage metrics.
- **Centralized Path Monitoring**.

#### **Python Agents**

1. **CHANGELOG Agent** (`agent_code_mon_changelog.py`)
   - Monitors file changes.
   - Analyzes code modifications and generates changelogs.
   - Git-aware (optional and automatic).
   - AI-powered analysis for smarter changelogs.

2. **README Agent** (`agent_code_mon_readme.py`)
   - Automatically generates module documentation.
   - Updates README files with API documentation.
   - AI-powered summaries with customizable markers.

3. **Dependency Graph Agent** (`agent_code_mon_deps.py`)
   - Maps and visualizes project dependencies.
   - Tracks module relationships.
   - AI-powered insights for efficient dependency management.

### **Frontend**

A responsive **Next.js web application** that provides:
- **Real-time agent status** monitoring.
- **Live log streaming** for instant feedback.
- **LLM metrics dashboard** for tracking agent performance.
- **Path management** interface for easy configuration.
- **Dark-themed UI** for an enhanced user experience.

---

## 📋 **Requirements**

### **Backend**
- Python 3.6+
- Git (optional)
- Required Python packages (see `requirements.txt`)
- Ollama (optional for AI features, supports most models)

### **Frontend**
- Node.js 18+
- npm or yarn
- Modern web browser

---

## ⚙️ **Configuration**

### **Backend Configuration** (`config.ini`)
- **Monitor path settings**: Define the paths to monitor.
- **Agent-specific configurations**: Customize agent behavior.
- **Ollama settings**: Configure AI model and retry settings.
- **Server options**: Modify server-related configurations.
- **AI content markers**: Define specific markers for AI outputs.

### **Frontend Configuration**
- **API endpoint**: `http://localhost:8000/api`
- **WebSocket endpoint**: `ws://localhost:8000/ws/logs`
- **Ollama endpoint**: `http://localhost:11434`

---

## 📝 **Development**

For detailed development setup and usage, check the respective documentation files:
- [Frontend Documentation](frontend/README.md)
- [Backend Documentation](docs/backend.md)

---

## 🛠️ **Troubleshooting**

### **Common Issues**

1. **Agent Start/Stop Issues**
   - Check file permissions.
   - Verify that Ollama is running (if using AI).
   - Review agent logs for errors.

2. **WebSocket Connection**
   - Ensure the backend is running.
   - Verify port availability.
   - Monitor WebSocket connection status and logs.

3. **Path Monitoring**
   - Use absolute paths in the configuration.
   - Check directory permissions and agent logs.

4. **LLM Service**
   - Ensure Ollama is functioning correctly.
   - Monitor queue metrics and review retry patterns in logs.

---

## 📝 **License**

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**. For more details, refer to the [LICENSE](LICENSE) file.

---

### Revolutionize the way you manage and document your code with AI-powered agents!
