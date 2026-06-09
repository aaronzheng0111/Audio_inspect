# Plan

现在进入技术阶段。在此阶段，您需向编码代理提供期望的技术栈、架构及限制条件，编码代理将据此生成完整的技术方案。若贵公司采用特定标准化技术，请在此说明；若需与遗留系统集成、存在合规要求或需达成的性能目标……所有这些需求均应在此明确。您还可要求生成多种方案变体，以便对比不同实现路径。若向编码代理开放内部文档，它能将您的架构模式与标准直接融入方案设计——毕竟编码代理必须先理解游戏规则，才能开始参与其中。

## Tech Requirements

### Env
    Uisng the conda environment to run the project.
    Create a conda env called "audio_visual_web"

### Front-End
    Using the React.js as the front-end interface.
        
    The whole interface UI design rules should follow the Google's Material Design. U shoudl remember Less is More while design the font, also it should have layers for the interface. And textures at the background make the whole interface looks fasion, tech and professinal.

    For visualize the graph, using the plotly library rendering the specific data attributes.

### Back-end
    Using the django as the backend server, once the user select some necessary attributes. The web-app would generate the graph for user to analysis.
