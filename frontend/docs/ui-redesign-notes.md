# NIA UI redesign notes

The redesign intentionally follows common patterns used by mature open-source AI chat interfaces:

- compact/collapsible conversation sidebar rather than a dashboard-like navigation area;
- narrow, centered message column with assistant messages rendered flat and user messages in a soft bubble;
- sticky/floating rounded prompt composer at the bottom of active conversations;
- dedicated empty-chat landing state with starter prompts;
- secondary details such as citations shown on demand instead of occupying a persistent panel;
- mobile sidebar becomes an overlay drawer and the centered desktop application frame becomes full-screen;
- voice session state is integrated immediately above the composer rather than consuming a permanent horizontal bar.

Reference implementations reviewed before this pass included Open WebUI, LibreChat, Vercel Chatbot / AI Elements, and LobeHub.
