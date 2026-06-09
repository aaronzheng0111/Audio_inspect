明确需求：您提供所构建产品的宏观描述及其背后的动机，编码代理将生成详细规格说明。这并非涉及技术栈或应用设计，而是聚焦于用户旅程、使用体验及成功标准。

谁将使用该产品？它能为用户解决什么问题？用户如何与之交互？哪些成果至关重要？可将其视为绘制理想用户体验蓝图，再由编码代理完善细节。关键在于，这份文档会随着您对用户及其需求的深入了解而持续进化，成为动态演进的活文档。

# Specify
This is the file record the reason and the target of purpose of building up the web-app. The target user is the researcher or data engineer who collect audio data and wanna process with it.

## Difficultly:

在做数据清洗的时候，单独针对不同的数据源进行处理是一项巨大的工程。不同的数据来源，不同的音频格式，不同的数据描述，csv table 拥有不同的attributes。各种各样的问题，大大的增加了Data Cleaning， Data Processing, and  Data Engineering的难度。


## Design

The whole web-app should include four steps:

1. Fetching the sample (or full) audios from the local device.
2. User could select data attributes to doing the analysis 
3. Using different visualization technique to help the user filter the datasets.
4. Generating the Simple report after filtering

## User
This web-app is used for the data engineer for cleaning and filterning the audios for process the ASR,TTS audio datasets.

## Successful result

After using this, user could reduce the time to doing select the data attributes， 

Doing the analysis of the data attributes

Using the new filter rules to check the differences.

Generate the new csv record audios after filtering

Generate a pdf report with the comparision

