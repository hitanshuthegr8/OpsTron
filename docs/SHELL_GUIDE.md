# Shell-Specific Commands Guide

## 🔍 Identify Your Shell

Run this command to see which shell you're using:
```bash
echo $0
```

Or check your terminal title bar.

---

## 📝 Commands by Shell Type

### **Git Bash** (Most Common on Windows)

#### Activate Virtual Environment
```bash
source venv/Scripts/activate
```

#### Deactivate
```bash
deactivate
```

#### Full Setup Commands
```bash
# Backend setup
cd /c/Users/HP/Desktop/Secret/Project/mvp2/backend
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
deactivate

# Agent setup
cd /c/Users/HP/Desktop/Secret/Project/mvp2/agent
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
cp config/.env.example config/.env
# Edit config/.env with your API keys
cd db
python load_runbooks.py
cd ..
deactivate

# Run backend (Terminal 1)
cd /c/Users/HP/Desktop/Secret/Project/mvp2/backend
source venv/Scripts/activate
python app.py

# Run agent (Terminal 2)
cd /c/Users/HP/Desktop/Secret/Project/mvp2/agent
source venv/Scripts/activate
python main.py
```

---

### **PowerShell**

#### Activate Virtual Environment
```powershell
venv\Scripts\Activate.ps1
```

Or if that fails:
```powershell
.\venv\Scripts\Activate.ps1
```

#### If you get execution policy error:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Deactivate
```powershell
deactivate
```

#### Full Setup Commands
```powershell
# Backend setup
cd c:\Users\HP\Desktop\Secret\Project\mvp2\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
deactivate

# Agent setup
cd c:\Users\HP\Desktop\Secret\Project\mvp2\agent
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config\.env.example config\.env
# Edit config/.env with your API keys
cd db
python load_runbooks.py
cd ..
deactivate

# Run backend (Terminal 1)
cd c:\Users\HP\Desktop\Secret\Project\mvp2\backend
.\venv\Scripts\Activate.ps1
python app.py

# Run agent (Terminal 2)
cd c:\Users\HP\Desktop\Secret\Project\mvp2\agent
.\venv\Scripts\Activate.ps1
python main.py
```

---

### **Command Prompt (CMD)**

#### Activate Virtual Environment
```cmd
venv\Scripts\activate.bat
```

#### Deactivate
```cmd
deactivate
```

#### Full Setup Commands
```cmd
REM Backend setup
cd c:\Users\HP\Desktop\Secret\Project\mvp2\backend
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
deactivate

REM Agent setup
cd c:\Users\HP\Desktop\Secret\Project\mvp2\agent
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
copy config\.env.example config\.env
REM Edit config/.env with your API keys
cd db
python load_runbooks.py
cd ..
deactivate

REM Run backend (Terminal 1)
cd c:\Users\HP\Desktop\Secret\Project\mvp2\backend
venv\Scripts\activate.bat
python app.py

REM Run agent (Terminal 2)
cd c:\Users\HP\Desktop\Secret\Project\mvp2\agent
venv\Scripts\activate.bat
python main.py
```

---

## ✅ Quick Fix for Your Current Situation

Since you're in `backend` directory and venv is created, try these in order:

### Option 1: Git Bash
```bash
source venv/Scripts/activate
```

### Option 2: PowerShell
```powershell
.\venv\Scripts\Activate.ps1
```

### Option 3: CMD
```cmd
venv\Scripts\activate.bat
```

### Option 4: Direct Python (Works Everywhere)
```bash
# Skip venv activation and use Python directly
venv/Scripts/python -m pip install -r requirements.txt
venv/Scripts/python app.py
```

---

## 🎯 Recommended: Use Git Bash

If you have Git installed, **Git Bash** is the most consistent shell for cross-platform commands.

To open Git Bash:
1. Right-click in your project folder
2. Select "Git Bash Here"
3. Use the Git Bash commands above

---

## 🔍 How to Tell If venv is Activated

When activated successfully, you'll see:
```
(venv) user@computer:/path/to/project$
```

The `(venv)` prefix indicates the virtual environment is active.
