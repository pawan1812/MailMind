# 📧 MailMind: A Simple Guide

Welcome! This guide explains how to easily understand and use **MailMind**. 

Think of MailMind as a flight simulator, but for an email inbox. You can plug your AI bot into MailMind to see how well it classifies emails, writes replies, and handles urgent tasks.

---

## 🎯 1. The Core Idea
When you connect to MailMind, your AI acts as an executive assistant. We offer 3 different challenges:

* **🟢 Easy Task (`classify_inbox`)**: The AI just needs to read 15 emails and tag them correctly (e.g., "Urgent", "Spam", "Meeting").
* **🟡 Medium Task (`draft_replies`)**: The AI needs to read 25 emails and actually write fitting replies based on who sent them.
* **🔴 Hard Task (`manage_inbox`)**: The AI gets 40 emails plus surprise "urgent alerts" that pop up mid-session! The AI must react quickly before deadlines expire.

**What is a good score?**
A top-tier AI should aim for a score near **`1.0`**. For reference, base AI models (like GPT-4o-Mini) currently score about **`0.58`** on average across all tasks.

---

## 🔌 2. Understanding the Interface (How to connect)

MailMind isn't a complex software—it's just a simple web API! Your code talks to MailMind using simple web requests. Here is the 4-step loop you need to build:

### Step 1: Start the Game (`POST /reset`)
You tell MailMind: *"Start the Medium task!"* 
MailMind generates a brand new inbox filled with fake emails specifically designed for testing, and hands you the first email.

### Step 2: Read the Screen (`GET /state`)
You ask MailMind: *"What's going on?"*
MailMind replies with all the details: The email subject, who sent it, the full message body, and how many tasks you have left to do.

### Step 3: Take Action (`POST /step`)
Now your AI decides what to do. You send MailMind a simple JSON action. For example:
```json
{
   "action_type": "draft_reply",
   "reply_body": "Hi there, I will review the Q3 budget right away.",
   "tone": "professional"
}
```
MailMind will instantly give you "points" inside a reward telling you if that was a smart move or a bad decision!

### Step 4: Get Your Report Card (`POST /grader`)
Once your AI processes every single email in the inbox, you call the grader. MailMind will grade your efficiency, accuracy, and tone to give you a final score between `0.0` and `1.0`.

---

## 💡 3. Quick Tips for Making Your AI Better
If you are writing the code that connects your AI to this interface, follow this simple flow:
1. **Always Check the Sender**: If an email comes from the CEO, make sure your bot chooses a `formal` tone!
2. **Don't Forget to Delete Spam**: You win points for spotting junk mail and deleting it immediately. 
3. **Watch Out for Injections (Hard Mode)**: Sometimes a new, urgent email pushes its way to the top of the pile. Write your code so your AI checks for new urgent emails before blindly answering old ones.
