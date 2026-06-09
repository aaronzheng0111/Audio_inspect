# Task
编码代理接收规格说明和计划后，将其分解为实际工作任务。它生成可审查的小块代码，每块代码都解决特定的难题。每个任务都应能独立实现并测试——这至关重要，因为它使编码代理能够验证工作成果并保持进度，如同为AI代理实施测试驱动开发流程。相较于笼统的“构建认证功能”，具体任务应明确为“创建验证邮箱格式的用户注册接口”。

The following number correspond in both front-end and back-end

## Front-End

    1.At the begining, there should a page tell user to input the audio csv path.

    2.And then, the second page shows the csv details and attributes to tick for next round, there won't be too many sample being shown like 15 rows would be enough.

    3. After showing the csv details, the There should be some attributes,which is necessary: audio_name_id, text, audio_path, and some evaluation metrics: RMS, LUFS, Dynamic Range, Segmental SNR, SRMR, C50, Spectral Flatness, ZCR. Then, the user tick the attributes it needs to be generated. also, the user could match the attributes for later process since some attributes name are not same as regular.

    4. Since the back-end predict the time to calculate the new attributes, user could select which attributes it need to click and whether continue process. (there should one 'ALL' tick box for user friendly.)

    5. After select the attributes, next page should have different cards shows the details of the attributes and graph. also, due to the large amount of data, user could select how many data being rendered(also could select randomly or first 200 rows etc.)


    For different graphs(scatter plot, bar graph etc.), there should be different card contains each of them.

    For adjust the values for filtering, there should be slide bar and could type the value to change also.





## Back-End

    1+2: Backend receive the csv path, and analysis the content and get sample send to front-end to rendering.

    3+4: After reviewing the inital csv, the user click the attributes that need to be generated, and change some attributes name maybe. The backend change the attributes name and also generate the new values for new attribues. The backend sent back the predict using time for the user.

    5. After selecting and calculating attributes, should generate a statistical table shows info about different attributes (for all data since it just a summary, not rendering too manly elements on the card)


