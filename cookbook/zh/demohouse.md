# Demo 展示厅

```{note}
在我们的 展示厅（Demo House） 中，您可以探索各种演示项目，展示如何使用 AgentScope Runtime 构建智能体应用。这些演示项目原先托管在本仓库中，如今已迁移至 [agentscope-ai/agentscope-samples](https://github.com/agentscope-ai/agentscope-samples)，以更好地展示它们与其他 AgentScope 库的集成与协作。
```

<div class="gallery-container">
    <a class="gallery-item"
       href="https://github.com/agentscope-ai/agentscope-samples/tree/main/browser_use/browser_use_fullstack_runtime">
        <div class="gallery-item-card">
            <div class="gallery-item-card-image-container">
                <img class="gallery-item-card-img"
                     src="https://img.alicdn.com/imgextra/i2/O1CN01M4Xm6S1PypUvcjzq5_!!6000000001910-0-tps-1598-1596.jpg"
                     alt="浏览器控制智能体">
            </div>
            <div class="gallery-item-card-content">
                <div class="gallery-item-card-title">浏览器控制智能体</div>
                <div class="gallery-item-description">
                    在AgentScope Runtime中使用浏览器沙箱创建一个网页浏览器控制智能体。
                </div>
            </div>
        </div>
    </a>
    <a class="gallery-item"
       href="https://github.com/agentscope-ai/agentscope-samples/tree/main/deep_research/qwen_langgraph_search_fullstack_runtime">
        <div class="gallery-item-card">
            <div class="gallery-item-card-image-container">
                <img class="gallery-item-card-img"
                     src="https://img.alicdn.com/imgextra/i2/O1CN01M4Xm6S1PypUvcjzq5_!!6000000001910-0-tps-1598-1596.jpg"
                     alt="Qwen LangGraph 搜索">
            </div>
            <div class="gallery-item-card-content">
                <div class="gallery-item-card-title">Qwen LangGraph 搜索
                </div>
                <div class="gallery-item-description">
                    在AgentScope Runtime中开发Qwen LangGraph搜索功能。
                </div>
            </div>
        </div>
    </a>
    <a class="gallery-item"
       href="https://github.com/agentscope-ai/agentscope-samples/tree/main/conversational_agents/chatbot_fullstack_runtime">
        <div class="gallery-item-card">
            <div class="gallery-item-card-image-container">
                <img class="gallery-item-card-img"
                     src="https://img.alicdn.com/imgextra/i2/O1CN01M4Xm6S1PypUvcjzq5_!!6000000001910-0-tps-1598-1596.jpg"
                     alt="多用户聊天机器人">
            </div>
            <div class="gallery-item-card-content">
                <div class="gallery-item-card-title">多用户聊天机器人</div>
                <div class="gallery-item-description">
                    使用AgentScope Runtime构建多用户聊天机器人。
                </div>
            </div>
        </div>
    </a>
</div>

<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .gallery-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 24px;
        margin: 32px 0;
        padding: 0 16px;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .gallery-item {
        text-decoration: none;
        color: inherit;
        display: block;
        transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    }

    .gallery-item-card {
        background: #ffffff;
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 16px;
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.02);
        backdrop-filter: blur(10px);
        position: relative;
        display: flex;
        flex-direction: column;
        height: 300px;
    }

    .gallery-item-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    .gallery-item:hover {
        transform: translateY(-8px) scale(1.02);;
    }

    .gallery-item:hover .gallery-item-card::before {
        opacity: 1;
    }

    .gallery-item-card-image-container {
        flex: 1;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        overflow: hidden;
    }

    .gallery-item-card-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        transition: transform 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    }

    .gallery-item:hover .gallery-item-card-img {
        transform: scale(1.05);
    }

    .gallery-item-card-content {
        flex: 1;
        padding: 20px 24px 24px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    .gallery-item-card-title {
        font-weight: 600;
        font-size: 18px;
        line-height: 1.4;
        color: #1d1d1f;
        margin: 0 0 12px;
        letter-spacing: -0.01em;
    }

    .gallery-item-description {
        color: #86868b;
        font-size: 14px;
        line-height: 1.6;
        font-weight: 400;
        letter-spacing: 0.01em;
    }

    @media (prefers-color-scheme: dark) {
        .gallery-item-card {
            background: rgba(28, 28, 30, 0.8);
            border-color: rgba(255, 255, 255, 0.1);
        }

        .gallery-item-card-title {
            color: #f5f5f7;
        }

        .gallery-item-description {
            color: #a1a1a6;
        }

        .gallery-item:hover .gallery-item-card {
            transform: scale(1.02);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08), 0 20px 60px rgba(0, 0, 0, 0.04);
            border-color: rgba(0, 122, 255, 0.1);
            border-radius: 16px;
        }
    }

    @media (max-width: 768px) {
        .gallery-container {
            grid-template-columns: 1fr;
            gap: 16px;
            margin: 24px 0;
            padding: 0 12px;
        }

        .gallery-item-card-content {
            padding: 16px 20px 20px;
        }

        .gallery-item-card-title {
            font-size: 16px;
            margin-bottom: 8px;
        }

        .gallery-item-description {
            font-size: 13px;
        }

        .gallery-item-card-image-container {
            height: 160px;
        }
    }

    @media (prefers-reduced-motion: no-preference) {
        html {
            scroll-behavior: smooth;
        }
    }

    .gallery-item:focus {
        outline: none;
    }

    .gallery-item:focus .gallery-item-card {
        box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.4), 0 8px 30px rgba(0, 0, 0, 0.08), 0 20px 60px rgba(0, 0, 0, 0.04);
    }

    .gallery-item-card {
        animation: fadeInUp 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
        opacity: 0;
        transform: translateY(20px);
    }

    .gallery-item:nth-child(1) .gallery-item-card {
        animation-delay: 0.1s;
    }

    .gallery-item:nth-child(2) .gallery-item-card {
        animation-delay: 0.2s;
    }

    .gallery-item:nth-child(3) .gallery-item-card {
        animation-delay: 0.3s;
    }

    @keyframes fadeInUp {
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
</style>
