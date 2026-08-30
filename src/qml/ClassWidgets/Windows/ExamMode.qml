import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import RinUI

Window {
    id: examModeWindow
    visible: true
    visibility: Window.FullScreen
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    minimumWidth: Screen.width
    minimumHeight: Screen.height
    maximumWidth: Screen.width
    maximumHeight: Screen.height
    color: "#000000"
    title: qsTr("考试模式")

    function exitExamMode() {
        AppCentral.examMode.exit()
    }

    onClosing: function(close) {
        close.accepted = false
        exitExamMode()
    }

    Component.onCompleted: {
        showFullScreen()
        requestActivate()
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: parent.width
        spacing: Math.max(12, parent.height * 0.018)

        Text {
            Layout.alignment: Qt.AlignHCenter
            color: "#ffffff"
            text: AppCentral.timeService.currentTime
            font.family: "Segoe UI"
            font.weight: Font.DemiBold
            font.pixelSize: Math.max(96, Math.min(examModeWindow.width * 0.17, 280))
            horizontalAlignment: Text.AlignHCenter
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            color: "#cbd5e1"
            text: {
                const dateParts = AppCentral.timeService.currentDate.split("-")
                if (dateParts.length !== 3)
                    return AppCentral.timeService.currentDate
                return Number(dateParts[0]) + qsTr(" 年 ")
                        + Number(dateParts[1]) + qsTr(" 月 ")
                        + Number(dateParts[2]) + qsTr(" 日")
            }
            font.family: "Segoe UI"
            font.pixelSize: Math.max(24, Math.min(examModeWindow.width * 0.03, 44))
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Button {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Math.max(36, parent.height * 0.06)
        text: qsTr("退出考试模式")
        onClicked: examModeWindow.exitExamMode()
    }
}
