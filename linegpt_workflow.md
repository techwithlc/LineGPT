## 🔄 LineGPT Workflow

The following diagram illustrates the architecture and data flow of the LineGPT application:

```mermaid
flowchart LR
    User(LINE User) <-->|Messages| LINE[LINE Platform]
    LINE <-->|Webhook Events| Server[LineGPT Server]
    Server -->|User Query| Process[Message Processing]
    Process -->|Command Handling| Commands{Commands}
    Process -->|Regular Message| Chat[Chat Processing]
    
    Commands -->|/chat| Chat
    Commands -->|/reset| Reset[Reset Conversation]
    Commands -->|/news| News[Financial News]
    Commands -->|/help| Help[Command List]
    
    Chat -->|API Request| OpenAI[OpenAI GPT API]
    OpenAI -->|AI Response| Chat
    
    News -->|API Request| FinAPI[Financial News API]
    FinAPI -->|News Data| News
    
    Chat -->|Format Response| Response[Format Response]
    News -->|Format News| Response
    Reset -->|Confirmation| Response
    Help -->|Command Info| Response
    
    Response -->|LINE Message| Server
    
    subgraph "Debug Endpoints"
    Debug[Debug Routes]
    Server -.->|Testing| Debug
    Debug -.->|Raw Message| LINE
    Debug -.->|Test Encoding| OpenAI
    end
    
    style User fill:#f9d71c,stroke:#333,stroke-width:2px
    style LINE fill:#00c300,stroke:#333,stroke-width:2px,color:#fff
    style Server fill:#5762d5,stroke:#333,stroke-width:2px,color:#fff
    style OpenAI fill:#74aa9c,stroke:#333,stroke-width:2px,color:#fff
    style FinAPI fill:#ff6b6b,stroke:#333,stroke-width:2px
    style Debug fill:#ff9e00,stroke:#333,stroke-width:2px
```

This diagram shows how user messages flow through the LINE platform to the LineGPT server, where they are processed based on command type, then routed to appropriate services (OpenAI API or Financial News API), and finally formatted and sent back to the user through LINE. 