import QtQuick 
import QtQuick.Controls 
import QtQuick.Layouts 
import QtQuick.Controls.Material
import QtCharts


// Main application window

ApplicationWindow {
    id: window                                      // main window
    visible: true                               // show window
    width: 980                                // window size
    height: 620                     // window size
    title: "SCADA Control Panel"        // window title
    background:                         // custom background
        Rectangle {                     // rounded rectangle
            color: "#12141A"  // dark background
            border.width: 10    // border width
        }               

    Material.theme: Material.Dark
    Material.primary: "#00E5FF"      // blue for primary elements
    Material.accent: "#00E5FF"          // blue for accent elements
    Material.foreground: "#E0E0E0"    // light gray for text/icons

    menuBar: MenuBar {
        
        Action {
            id: openAction
            text: "Exit"
            shortcut: "Ctrl+Q"
            onTriggered: Qt.quit()
        }      
        Menu {
            title: "File"

            MenuItem {
                action: openAction
            }

            // MenuItem { 
            //     text: "Exit" 
            //     shortcut: "Ctrl+Q"
            //     onTriggered: Qt.quit() 
            // }
        }
        
        Menu {
            title: "Help"
            MenuItem { 
                text: "About" 
                onTriggered: aboutDialog.open() 
            }
            MenuSeparator { }
            MenuItem { 
                text: "Version: " + appInfo.version
                enabled: false // Just text, not clickable
            }
        }
    }

    // About dialog
    Dialog {
        id: aboutDialog
        title: "About"
        padding: 20
        anchors.centerIn: parent
        standardButtons: Dialog.Ok
        
        // columnLayout: Column {
        Column {
            spacing: 10
            Label { text: "SCADA Motor Controller" ; font.bold: true }
            Label { text: "Version: " + appInfo.version }
            Label { text: "Python " + appInfo.pythonVersion + " + PySide6" }
        }
    }

    footer: ToolBar {
        height: 30
        background: Rectangle { color: "#f0f0f0" }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            
            Rectangle {
                width: 10; height: 10
                radius: 5
                // color: motorController.isConnected ? "green" : "red"
                color: motorController.state == "OFF" ? "red" : "green"
            }
            
            Label {
                // text: motorController.isConnected ? "Port: " + motorController.currentSerialNumber : "Connection lost"
                color: motorController.state == "OFF" ? "red" : "green"
                text: motorController.state != "OFF" ? "Motor: " + motorController.currentSerialNumber : "Connection lost"
                font.pixelSize: 11
            }
            
            Item { Layout.fillWidth: true } // Spacer
            
            Label {
                color: "blue"
                text: "CPU: " + appInfo.cpuLoad  // If you add such a metric in Python
                font.pixelSize: 11
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // 1. Панель вкладок сверху
        TabBar {
            id: mainTabBar
            Layout.fillWidth: true
            TabButton { text: "🕹 CONTROL" }
            TabButton { text: "📋 LOGS" }
        }

        // 2. Контейнер для содержимого вкладок
        StackLayout {
            currentIndex: mainTabBar.currentIndex
            Layout.fillWidth: true
            Layout.fillHeight: true

            // --- ВКЛАДКА 1: УПРАВЛЕНИЕ (Ваш текущий RowLayout) ---
            Item {
                RowLayout {
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    anchors.fill: parent            // Fill entire window
                    anchors.margins: 4
                    spacing: 2              //  Spacing between panels

                    ScrollView {
                        id: motorScroll                                 //  Scrollable area
                        Layout.preferredWidth: parent.width * 0.55   // Left panel takes 55% width
                        Layout.fillHeight: true                     // Fill height
                        clip: true                                  // important! clips (cuts) content outside
                        ScrollBar.vertical.policy: ScrollBar.AsNeeded  // vertical scrollbar as needed  
                        // ScrollBar.horizontal.policy: ScrollBar.Never     // no horizontal scrollbar
                        ScrollBar.horizontal.policy: ScrollBar.AsNeeded     // no horizontal scrollbar

                // ── Left panel - Motor ───────────────────────────────
                        Pane {

                            // Layout.preferredWidth: parent.width * 0.55
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            // width: parent.width           // important for horizontal alignment inside ScrollView
                            width: motorScroll.availableWidth  // important for horizontal alignment inside ScrollView
                            height: parent.height      // important for vertical alignment inside ScrollView
                            padding: 16                 // padding inside panel
                            Material.background: Material.CardBackground  // Material card style

                            Material.elevation: 4           // shadow depth 
                            background: Rectangle {
                                color: "#1E222D" // Цвет "стальной пластины" [cite: 10]
                                radius: 2
                                border.color: "#3A414D" // Тонкая рамка [cite: 11, 14]
                                border.width: 1
                                
                                // Внутренний градиент или блик сверху
                                Rectangle {
                                    anchors.top: parent.top
                                    width: parent.width; height: 1
                                    color: "#3D4454" // Эффект фаски
                                }
                            }



                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 12                  // spacing between elements
                                Label { 
                                    text: "MOTOR CONTROL UNIT"
                                    font.bold: true
                                    font.pixelSize: 12
                                    color: "#8A919E"
                                }
                                // Motor status
                                RowLayout {                                // motor status row            
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 40
                                        color: "#161920"
                                        border.color: "#333"
                                        RowLayout {
                                            anchors.centerIn: parent
                                            spacing: 10
                                            Rectangle { width: 12; height: 12; radius: 6; color: motorController.isMoving ? "#00FF41" : "#2196F3" }
                                            Label { text: motorController.state; font.pixelSize: 14; font.bold: true }
                                        }
                                    
                                        // Label { text: "Motor Status:"; font.bold: true }        // bold label
                                        // Rectangle {                     // status indicator
                                        //     width: 18; height: 18; radius: 9                // circle shape
                                        //     color: {
                                        //         switch(motorController?.state ?? "OFF") {
                                        //             case "RUNNING": return "#4CAF50"
                                        //             case "WARNING": return "#FF9800"
                                        //             case "ERROR":   return "#F44336"
                                        //             case "IDLE":    return "#2196F3"
                                        //             default:        return "#757575"
                                        //         }
                                        //     }
                                        // }
                                        // Label {
                                        //     text: motorController?.state ?? "OFF"   // dynamic status text
                                        //     color: "#ffffff"
                                        // }
                                    }
                                }

                                RowLayout {                                         // motor selection row

                                    Label { text: "Select Motor by S/N:" }           // label for motor selection          
                                    ComboBox {
                                        id: motorSelector
                                        Layout.fillWidth: false                      // fill width  
                                        model: motorController.availableMotors      // model from MotorController
                                        // textRole: "sn"
                                        // model: motorController.availableMotorObjects      // model from MotorController
                                        enabled: !motorController.isMoving;
                                        // textRole: "serialNumber"                     // use serialNumber role for display
                                        currentIndex: model ? model.indexOf(motorController.currentSerialNumber) : -1        // set current index based on selected motor
                                        onActivated: (index) => {
                                            let selectedSn = model[index]                     // get selected serial number 
                                            if (selectedSn !== undefined) {         // check for valid selection
                                                motorController.currentSerialNumber = selectedSn          // update selected motor in controller
                                                console.log("Motor selected: " + selectedSn + " (index: " + index + ")")
                                            } else {
                                                console.warn("Attempted to select undefined index: " + index)
                                            }

                                            // motorController.currentSerialNumber = model[index]                      // update selected motor in controller
                                            // console.log("Port selected: " + "number " + index + " " + model[index])
                                        }
                                        font.pixelSize: 14
                                    }
                                }
                                RowLayout {
                                    Label { text: "Current Limit (mA):" }
                                    SpinBox { 
                                        id: currentLimit; 
                                        from: 1; to: 9000; value: 5000; editable: true 
                                        onValueModified:{
                                            let val = value;
                                            if (!isNaN(val) && val !== null) {
                                                motorController.currentLimit = val;
                                            }
                                            console.log("Current limit updated to " + val + " mA")
                                        }
                                    }
                                    Label { text: "Actual current (mA):" }
                                    TextField { readOnly: true; color: "#FFA500"; text: motorController?.actualCurrent ?? "—" }
                                }
                                
                                //  Absolute move controls
                                RowLayout {                     // absolute move row
                                    Label { text: "Destination position:" }     // label for destination position
                                    TextField {                                 
                                        id: targetPos
                                        Layout.fillWidth: true                 // fill width    
                                        placeholderText: "Destination position" // placeholder text
                                        inputMethodHints: Qt.ImhDigitsOnly      // numeric input only
                                        validator: IntValidator{bottom: -100000; top: 100000}
                                    }
                                    Button {
                                        text: "Move Absolute"
                                        enabled: !motorController.isMoving
                                        onClicked: {
                                            let pos = parseInt(targetPos.text) || 0
                                            motorController.moveAbsolute(pos, velocity.value, acceleration.value, timeoutEnable.checked ? timeout.value : 0)
                                        }
                                    }
                                }

                                // Motion controls buttons
                                RowLayout {
                                    spacing: 8
                                    
                                    Button { text: "◀ Backward";  enabled: !motorController.isMoving; onClicked: { motorController.moveBackward(velocity.value, acceleration.value, timeoutEnable.checked ? timeout.value : 0); console.log("Backward pressed") } }
                                    Button { text: "■ STOP";      highlighted: true; Material.background: Material.Red;  onClicked: { motorController.stop(); console.log("Stop pressed");}}
                                    Button { text: "Forward ▶"; enabled: !motorController.isMoving; onClicked: { motorController.moveForward(velocity.value, acceleration.value, timeoutEnable.checked ? timeout.value : 0); console.log("Forward pressed") }}
                                    Button { text: "Home"; enabled: !motorController.isMoving; onClicked: { motorController.home(); console.log("Home pressed") } }
                                }

                                GridLayout {
                                    columns: 4
                                    Layout.fillWidth: true
                                    // enabled: !motorController.isMoving   // Disable while motor is moving
                                    opacity: enabled ? 1.0 : 0.5 // Visual feedback when disabled
                                    Behavior on opacity { NumberAnimation { duration: 200 } }

                                    Label { text: "Velocity:" }
                                    SpinBox { enabled: !motorController.isMoving; id: velocity; from: 1; to: 30000; value: 1000; editable: true }


                                    Label { text: "Current velocity:" }
                                    TextField { readOnly: true; color: "#FFA500"; text: motorController?.velocity ?? "—" }

                                    Label { text: "Acceleration:" }
                                    SpinBox { enabled: !motorController.isMoving; id: acceleration; from: 10; to: 10000; value: 2000; editable: true }
                                    // Item { Layout.fillWidth: true }    // Spacer to push controls to the left, and prevent stretching of spinboxes when resizing
                                    // Item { Layout.fillWidth: true } 

                                    Label { text: "Current torque:" }
                                    TextField { readOnly: true; color: "#FFA500"; text: motorController?.actualTorque ?? "—" }


                                }

                                Rectangle { Layout.fillWidth: true; height: 1; color: "#444" }

                                // Current values
                                GridLayout {
                                    columns: 2
                                    Label { text: "Current position:" }
                                    // TextField { readOnly: true; text: motorController.currentMotor?.position ?? "—" }
                                    TextField { readOnly: true; color: "#FFA500"; text: motorController?.position ?? "—" }

                                    
                                    // Label { text: "Current velocity:" }
                                    // TextField { readOnly: true; text: motorController?.velocity ?? "—" }

                                    Label { text: "Running time:" }
                                    TextField { id: runtimeDisplay; readOnly: true; color: "#FFA500"; text: "00:00:00" }
                                }

                                Timer {
                                    id: runningTimer
                                    interval: 1000 // 1 second
                                    // running: motorController.isMoving // Timer runs while the motor is moving
                                    running: motorController.state === "RUNNING"  //
                                    repeat: true
                                    
                                    property int seconds: 0

                                    onTriggered: {          // Increment runtime every second
                                        seconds++;
                                        runtimeDisplay.text = formatTime(seconds);
                                    }
                                    
                                    // Reset when movement starts
                                    onRunningChanged: {         // Reset seconds when motor starts moving
                                        if (running) {
                                                seconds = 0; 
                                            runtimeDisplay.text = "00:00:00";
                                        }
                                    }

                                    function formatTime(s) {
                                        let h = Math.floor(s / 3600).toString().padStart(2, '0');
                                        let m = Math.floor((s % 3600) / 60).toString().padStart(2, '0');
                                        let sec = (s % 60).toString().padStart(2, '0');
                                        return h + ":" + m + ":" + sec;
                                    }
                                }

                                CheckBox {
                                    id: timeoutEnable
                                    text: "Enable timeout"
                                }

                                RowLayout {
                                    enabled: timeoutEnable.checked
                                    Label { text: "Timeout (s):" }
                                    SpinBox { id: timeout; from: 1; to: 3600; value: 30; editable: true }
                                }
                            }
                        }

                    }


                    // ── Правая панель: Scale ──────────────────────────────
                    Pane {
                        id: scalePanel
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        background: Rectangle {
                            color: "#1E222D" // Цвет "стальной пластины" [cite: 10]
                            radius: 4
                            border.color: "#3A414D" // Тонкая рамка [cite: 11, 14]
                            border.width: 1
                            
                            // Внутренний градиент или блик сверху
                            Rectangle {
                                anchors.top: parent.top
                                width: parent.width; height: 1
                                color: "#3D4454" // Эффект фаски
                            }
                        }

                        ScrollView {
                            id: scaleScroll
                            anchors.fill: parent
                            clip: true
                            contentWidth: availableWidth

                            ColumnLayout {
                                // width: scrollView.width   // ← neccesary for horizontal alignment
                                // height: scrollView.height // ← do not set height, if want it expand naturally
                                width: scaleScroll.availableWidth // fill width of scroll area for proper alignment
                                // height: scaleScroll.availableHeight // do not set height, if want it expand naturally
                                spacing: 16
                                anchors.fill: parent
                                anchors.margins: 12
                                Label { text: "MEASUREMENT UNIT"; font.bold: true; font.pixelSize: 12; color: "#8A919E" }
                                RowLayout {
                                    Label { text: "Scale Status:"; font.bold: true }
                                    Rectangle {
                                        width: 18; height: 18; radius: 9
                                        color: scaleController.isConnected ? "#4CAF50" : "#F44336"
                                    }
                                    Label { text: scaleController.isConnected ? "CONNECTED" : "DISCONNECTED" }
                                }
                                
                                Label { text: "Select Port:" }
                                ComboBox {
                                    Layout.fillWidth: true
                                    model: scaleController.availablePorts // model from ScaleController
                                    // currentIndex: model.indexOf(scaleController.currentSerialPort)
                                    currentIndex: model ? model.indexOf(scaleController.currentSerialPort) : -1   // handle empty model case, if no scales found
                                    onActivated: (index) => {
                                        scaleController.update_serial_port(model[index])
                                        scaleController.connect()
                                        console.log("Port selected: " + "number " + index + " " + model[index])
                                    }
                                }
                                
                                GridLayout {
                                    columns: 4
                                    Layout.fillWidth: true
                                    // enabled: !motorController.isMoving   // Disable while motor is moving
                                    opacity: enabled ? 1.0 : 0.5 // Visual feedback when disabled
                                    Behavior on opacity { NumberAnimation { duration: 200 } }
                                    Label { text: "Weight:" }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 30
                                        color: "#0A0B0E" // Почти черный "экран"
                                        border.color: "#444"
                                        radius: 4

                                        Label {
                                            anchors.centerIn: parent
                                            // text: scaleController.weight.toFixed(5) + " kg"
                                            text: scaleController.weight.toFixed(3)  + " kg"
                                            // color: "#00E5FF" // Цифровой голубой
                                            color: "#FFA500" // Оранжевый для производных данных
                                            font.pixelSize: 20
                                            minimumPixelSize: 8
                                            fontSizeMode: Text.Fit
                                            font.family: "Courier New"
                                        }
                                    }
                                    // TextField {
                                    //     id: weightDisplay
                                    //     Layout.fillWidth: true
                                    //     readOnly: true
                                    //     color: "#00E5FF" // Neon blue color for weight display
                                    //     font.family: "Courier New" // Industrial style
                                    //     font.pixelSize: 32
                                    //     background: Rectangle { color: "#0A0C10"; radius: 2 }
                                    //     horizontalAlignment: Text.AlignHCenter
                                    //     text: scaleController.weight ? scaleController.weight.toFixed(2) + " kg" : "—"
                                    // }


                                    Label { text: "I =" }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 30
                                        color: "#0A0B0E" // Почти черный "экран"
                                        border.color: "#444"
                                        radius: 4

                                        Label {
                                            anchors.centerIn: parent
                                            // text: scaleController.weight.toFixed(5) + " kg"
                                            text: motorController.actualCurrent + " mA"
                                            // color: "#00E5FF" // Цифровой голубой
                                            color: "#FFA500" // Оранжевый для производных данных
                                            font.pixelSize: 20
                                            minimumPixelSize: 8
                                            fontSizeMode: Text.Fit
                                            font.family: "Courier New"
                                        }
                                    }
                                }

// ================================================ 
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.alignment: Qt.AlignHCenter
                                    spacing: 18


// ================================================Gauge component================================================
                                    
                                    ColumnLayout {
                                        spacing: 8
                                        Label {
                                            text: "RPM"
                                            color: "#8A919E"
                                            font.pixelSize: 12
                                            font.bold: true
                                            Layout.alignment: Qt.AlignHCenter
                                        }

                                        Rectangle {
                                            id: velocityGauge
                                            Layout.fillWidth: true
                                            Layout.preferredWidth: 260
                                            Layout.preferredHeight: 260
                                            color: "#161920"
                                            border.color: "#3A414D"
                                            border.width: 1
                                            radius: 6

                                            property real minValue: 0
                                            property real maxValue: 30000
                                            property real value: Math.abs(Number(motorController.velocity))
                                            property real safeValue: isNaN(value) ? 0 : Math.max(minValue, Math.min(maxValue, value))
                                            property real ratio: (safeValue - minValue) / (maxValue - minValue)
                                            // Label {
                                            //     anchors.top: parent.top
                                            //     anchors.horizontalCenter: parent.horizontalCenter
                                            //     anchors.topMargin: 10
                                            //     text: "RPM"
                                            //     color: "#8A919E"
                                            //     font.pixelSize: 12
                                            //     font.bold: true
                                            // }

                                            Canvas {
                                                id: gaugeCanvas
                                                anchors.fill: parent
                                                anchors.margins: 16

                                                property real gaugeValue: velocityGauge.safeValue

                                                onGaugeValueChanged: requestPaint()
                                                onWidthChanged: requestPaint()
                                                onHeightChanged: requestPaint()

                                                onPaint: {
                                                    const ctx = getContext("2d")
                                                    ctx.reset()

                                                    const w = width
                                                    const h = height
                                                    const cx = w / 2
                                                    const cy = h / 2
                                                    const r = Math.min(w, h) / 2 - 10

                                                    const startAngle = Math.PI * 0.75
                                                    const endAngle = Math.PI * 2.25
                                                    const valueAngle = startAngle + (endAngle - startAngle) * velocityGauge.ratio

                                                    ctx.lineCap = "round"

                                                    ctx.beginPath()
                                                    ctx.strokeStyle = "#2A313D"
                                                    ctx.lineWidth = 16
                                                    ctx.arc(cx, cy, r, startAngle, endAngle, false)
                                                    ctx.stroke()

                                                    ctx.beginPath()
                                                    ctx.strokeStyle = "#00E5FF"
                                                    ctx.lineWidth = 16
                                                    ctx.arc(cx, cy, r, startAngle, valueAngle, false)
                                                    ctx.stroke()

                                                    for (let i = 0; i <= 10; i++) {
                                                        const a = startAngle + (endAngle - startAngle) * (i / 10.0)
                                                        const r1 = r - 18
                                                        const r2 = r - 4
                                                        const x1 = cx + Math.cos(a) * r1
                                                        const y1 = cy + Math.sin(a) * r1
                                                        const x2 = cx + Math.cos(a) * r2
                                                        const y2 = cy + Math.sin(a) * r2

                                                        ctx.beginPath()
                                                        ctx.strokeStyle = "#7E8794"
                                                        ctx.lineWidth = 2
                                                        ctx.moveTo(x1, y1)
                                                        ctx.lineTo(x2, y2)
                                                        ctx.stroke()
                                                    }

                                                    ctx.beginPath()
                                                    ctx.fillStyle = "#0F1117"
                                                    ctx.arc(cx, cy, 10, 0, Math.PI * 2, false)
                                                    ctx.fill()

                                                    const nr = r - 28
                                                    const nx = cx + Math.cos(valueAngle) * nr
                                                    const ny = cy + Math.sin(valueAngle) * nr

                                                    ctx.beginPath()
                                                    ctx.strokeStyle = "#FFA500"
                                                    ctx.lineWidth = 4
                                                    ctx.moveTo(cx, cy)
                                                    ctx.lineTo(nx, ny)
                                                    ctx.stroke()
                                                }

                                                Component.onCompleted: requestPaint()
                                            }

                                            Column {
                                                anchors.centerIn: parent
                                                spacing: 4

                                                // Label {
                                                //     anchors.horizontalCenter: parent.horizontalCenter
                                                //     text: "RPM"
                                                //     color: "#8A919E"
                                                //     font.pixelSize: 12
                                                //     font.bold: true
                                                // }

                                                Label {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: Math.round(velocityGauge.safeValue)
                                                    color: "#00E5FF"
                                                    font.pixelSize: 34
                                                    font.family: "Courier New"
                                                    font.bold: true
                                                }

                                                Label {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: "0 - 30000"
                                                    color: "#6F7782"
                                                    font.pixelSize: 10
                                                }
                                            }
                                        }
                                    }
    // ================================================



    // ================================================================ROC bar component================================================
                                    ColumnLayout {
                                        Layout.preferredWidth: 90
                                        Layout.preferredHeight: 300
                                        spacing: 8

                                        Label {
                                            anchors.top: parent.top
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            anchors.topMargin: 10
                                            text: "ROC"
                                            color: "#8A919E"
                                            font.pixelSize: 12
                                            font.bold: true
                                        }

                                        Rectangle {
                                            id: rocBar
                                            Layout.preferredWidth: 90
                                            Layout.preferredHeight: 260
                                            color: "#161920"
                                            border.color: "#3A414D"
                                            border.width: 1
                                            radius: 6

                                            property real minValue: 0
                                            property real maxValue: 50
                                            property real value: Number(scaleController.ROC)
                                            property real safeValue: isNaN(value) ? 0 : Math.max(minValue, Math.min(maxValue, value))
                                            property real ratio: (safeValue - minValue) / (maxValue - minValue)

                                            // Label {
                                            //     anchors.top: parent.top
                                            //     anchors.horizontalCenter: parent.horizontalCenter
                                            //     anchors.topMargin: 10
                                            //     text: "ROC"
                                            //     color: "#8A919E"
                                            //     font.pixelSize: 12
                                            //     font.bold: true
                                            // }

                                            Rectangle {
                                                id: barTrack
                                                anchors.top: parent.top
                                                anchors.bottom: parent.bottom
                                                anchors.topMargin: 36
                                                anchors.bottomMargin: 36
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                width: 28
                                                radius: 4
                                                color: "#0A0B0E"
                                                border.color: "#444"

                                                Rectangle {
                                                    anchors.bottom: parent.bottom
                                                    anchors.left: parent.left
                                                    anchors.right: parent.right
                                                    height: parent.height * rocBar.ratio
                                                    radius: 4
                                                    color: "#00E5FF"
                                                }

                                                Repeater {
                                                    model: 6
                                                    Rectangle {
                                                        width: 10
                                                        height: 1
                                                        color: "#7E8794"
                                                        anchors.right: parent.left
                                                        anchors.rightMargin: 6
                                                        // y: (barTrack.height - height) - (index * (barTrack.height / 5))
                                                        y: barTrack.y + (barTrack.height - height) - (index * (barTrack.height / 5))

                                                    }
                                                }
                                            }
                                            Repeater {
                                                model: 6

                                                Label {
                                                    required property int index

                                                    // text: (rocBar.maxValue * (5 - index) / 5).toFixed(0)
                                                    text: (rocBar.maxValue * (index) / 5).toFixed(0)
                                                    color: "#6F7782"
                                                    font.pixelSize: 10

                                                    anchors.right: barTrack.left
                                                    anchors.rightMargin: 14

                                                    y: barTrack.y + (barTrack.height - height) - (index * (barTrack.height / 5)) - height / 2
                                                }
                                            }

                                            // Column {
                                            //     anchors.right: barTrack.left
                                            //     anchors.rightMargin: 14
                                            //     anchors.verticalCenter: barTrack.verticalCenter
                                            //     spacing: 31

                                            //     Repeater {
                                            //         model: 6
                                            //         Label {
                                            //             required property int index
                                            //             // text: (rocBar.maxValue * (5 - index) / 5).toFixed(1)
                                            //             text: (rocBar.maxValue * (5 - index) / 5)
                                            //             color: "#6F7782"
                                            //             font.pixelSize: 10
                                            //         }
                                            //     }
                                            // }

                                        }
                                        Label {
                                            Layout.alignment: Qt.AlignHCenter
                                            text: rocBar.safeValue.toFixed(3) + " L/min"
                                            color: "#FFA500"
                                            font.pixelSize: 16
                                            font.family: "Courier New"
                                            font.bold: true
                                        }
                                    }
                                }

    
// ================================================


                                // Label { text: "rpm=" }
                                // Rectangle {
                                //     Layout.fillWidth: true
                                //     height: 90
                                //     color: "#0A0B0E" // Почти черный "экран"
                                //     border.color: "#444"
                                //     radius: 4

                                //     Label {
                                //         anchors.centerIn: parent
                                //         // text: scaleController.weight.toFixed(5) + " kg"
                                //         text: motorController.velocity + " rpm"
                                //         color: "#00E5FF" // Цифровой голубой
                                //         // font.pixelSize: 80
                                //         font.pixelSize: 20
                                //         minimumPixelSize: 8
                                //         fontSizeMode: Text.Fit
                                //         font.family: "Courier New"
                                //     }
                                // }



                                // Label { text: "Q(dw/dt)=" }
                                // Rectangle {
                                //     Layout.fillWidth: true
                                //     height: 90
                                //     color: "#0A0B0E"
                                //     border.color: "#444"
                                //     Label {
                                //         anchors.centerIn: parent
                                //         // text: "Rate of Change (ROC): " + (motorController.isMoving ? (scaleController.weight / runningTimer.seconds).toFixed(2) : "0.00") + " kg/s"
                                //         // text: "Rate of Change (ROC): " + (motorController.isMoving ? (scaleController.ROC).toFixed(2) : "0.00") + " kg/s"
                                //         // text: "Q = " + (scaleController.ROC).toFixed(5)  + " l/m"
                                //         text: (scaleController.ROC).toFixed(3) + " L/min"
                                //         // color: "#FFA500" // Оранжевый для производных данных
                                //         color: "#00E5FF" // Blue
                                //         font.pixelSize: 20
                                //         // font.pixelSize: 80
                                //         minimumPixelSize: 8
                                //         fontSizeMode: Text.Fit

                                //     }
                                // }

                                
                                // TextField {
                                //     Layout.fillWidth: true
                                //     readOnly: true
                                //     color: "#00E5FF" // Neon blue color for weight display
                                //     font.family: "Courier New" // Industrial style
                                //     font.pixelSize: 32
                                //     background: Rectangle { color: "#0A0C10"; radius: 2 }
                                //     // text: "Rate of Change by Weight (ROC) - Weight/Time"
                                //     text: {
                                //         if ( motorController.isMoving && scaleController.weight !== undefined && runningTimer.seconds > 0) {
                                //             let power = scaleController.weight / runningTimer.seconds; // kg/s
                                //             return power.toFixed(2) + " kg/s"
                                //         } else {
                                //             return "Rate of Change by Weight (ROC) - Weight/Time"
                                //         }
                                //     }
                                // }

                                // Item { Layout.fillHeight: true }    // Spacer to push chart to the bottom, and prevent stretching when resizing

                                RowLayout {
                                    Label { text: "Poll interval (ms):" }
                                    SpinBox {
                                        from: 100; to: 5000; value: 500; stepSize: 100; editable: true
                                        onValueModified:{
                                            let val = value / 1000;
                                            if (!isNaN(val) && val !== null) {
                                                scaleController.update_poll_interval(val); // convert ms to s
                                            }
                                            // scaleController.update_poll_interval(value / 1000)   // convert ms to s
                                            console.log("Poll interval updated to " + value + " ms")
                                        } 
                                    }
                                }
                                
                                // ChartView {
                                //     id: rocChart
                                //     title: "Rate of Change (ROC)"
                                //     // anchors.fill: parent // or set specific width/height 
                                //     Layout.fillWidth: true
                                //     Layout.fillHeight: true
                                //     Layout.preferredHeight: 500 // minimum height for good visibility
                                //     enabled: !motorController.isMoving;

                                //     antialiasing: true
                                //     theme: ChartView.ChartThemeLight

                                //     ValueAxis {
                                //         id: axisX
                                //         min: 0
                                //         max: 500 // Количество точек на экране
                                //         labelFormat: " " // Скрываем цифры времени, если они не важны
                                //     }

                                //     ValueAxis {
                                //         id: axisY
                                //         min: 0
                                //         max: 10 // Настройте под ваши рабочие диапазоны ROC
                                //         labelsColor: "#2ecc71"
                                //     }

                                //     ValueAxis {
                                //         id: axisVY
                                //         min: 0
                                //         max: 20000 // velocity
                                //         labelsColor: "#652ecc"
                                //     }

                                //     ValueAxis {
                                //         id: axisCY
                                //         min: 0
                                //         max: 5000 // current
                                //         labelsColor: "#cc2e87"

                                //     }

                                //     // ValueAxis {
                                //     //     id: axisWY
                                //     //     min: 0
                                //     //     max: 10 // current
                                //     //     labelsColor: "#b4cc2e"

                                //     // }


                                //     LineSeries {
                                //         id: rocSeries
                                //         name: "ROC (l/min)"
                                //         axisX: axisX
                                //         axisY: axisY
                                //         color: "#2ecc71"
                                //         width: 2
                                //     }
                                //     LineSeries {
                                //         id: velSeries
                                //         name: "rpm (round/min)"
                                //         axisX: axisX
                                //         axisY: axisVY
                                //         color: "#652ecc"
                                //         width: 2
                                //     }
                                //     LineSeries {
                                //         id: curSeries
                                //         name: "Current (mA)"
                                //         axisX: axisX
                                //         axisY: axisCY
                                //         color: "#cc2e87"
                                //         width: 2
                                //     }

                                //     // LineSeries {
                                //     //     id: weiSeries
                                //     //     name: "Weight (kg)"
                                //     //     axisX: axisX
                                //     //     axisY: axisWY
                                //     //     color: "#b4cc2e"
                                //     //     width: 2
                                //     // }



                                //     // Вспомогательная переменная для отслеживания "времени" (оси X)
                                //     property int scrollTick: 0

                                //     // Сама функция обновления
                                //     function updateChart(newRoc, newVel, newCur, newWei) {
                                //         scrollTick++;
                                        
                                //         // Добавляем новую точку
                                //         rocSeries.append(scrollTick, newRoc);
                                //         velSeries.append(scrollTick, newVel);
                                //         curSeries.append(scrollTick, newCur);
                                //         // weiSeries.append(scrollTick, newWei);

                                //         // Если точек набралось больше, чем max оси X
                                //         if (scrollTick > axisX.max) {
                                //             // Сдвигаем окно видимости осей
                                //             axisX.min++;
                                //             axisX.max++;
                                            
                                //             // Удаляем самую старую точку из памяти, чтобы список не рос вечно
                                //             if (rocSeries.count > 120) { // Держим чуть больше, чем max, для плавности
                                //                 rocSeries.remove(0);
                                //                 velSeries.remove(0);
                                //                 curSeries.remove(0);
                                //                 // weiSeries.remove(0);
                                //             }
                                //         }
                                //     }

                                //     // Подключаемся к сигналу из Python
                                //     Connections {
                                //         target: scaleController
                                //         function onRocChanged() {
                                //             rocChart.updateChart(scaleController.ROC, motorController.velocity, 
                                //                         motorController.actualCurrent, scaleController.weight);
                                //         }
                                //     }
                                // }

                            }
                        }
                    }
                }
            }
            Item {
                Rectangle {
                    anchors.fill: parent
                    color: "#0F1117"
                    Label {
                        anchors.centerIn: parent
                        text: "System Logs will be here..."
                        color: "#8A919E"
                    }
                }    
            }
        }
    }
    // Connections {
    //     // Call this method from Python side to update target motor when selection changes
    //     target: motorController.get_motor_by_index(motorSelector.currentIndex)

    //     onPositionChanged: (p) => { 
    //         console.log("Position updated to: " + p);}
    // }
}
