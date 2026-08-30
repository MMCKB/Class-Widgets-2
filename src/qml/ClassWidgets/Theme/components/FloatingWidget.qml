import QtQuick
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects
import RinUI
import ClassWidgets.Theme 1.0

// 独立的单例内容组件。外壳直接复用当前主题的 Widget，主题只需覆盖
// ClassWidgets/theme/components/FloatingWidget.qml 即可定制浮窗内容。
Widget {
    id: root

    implicitWidth: floatingLayout.implicitWidth + 48
    implicitHeight: floatingLayout.implicitHeight + 32
    height: implicitHeight
    // text: "sdf"

    property var countdown: AppCentral.scheduleRuntime.remainingTime || { "minute": 0, "second": 0 }
    property color currentColor: {
        if (AppCentral.scheduleRuntime.currentSubject.color)
            return AppCentral.scheduleRuntime.currentSubject.color
        switch (AppCentral.scheduleRuntime.currentStatus) {
        case "free":
        case "break":
            return "#46CEA3"
        case "class":
            return "#D28B59"
        case "preparation":
            return "#9151d8"
        default:
            return "#605ed2"
        }
    }

    backgroundArea: Rectangle {
        id: circle
        width: root.height * 0.4
        height: root.height * 0.4
        x: (parent.width - width) / 2
        y: (parent.height - height) * 0.67
        radius: height / 2
        color: currentColor
        visible: lightingEffect

        layer.enabled: true
        layer.effect: FastBlur {
            anchors.fill: circle
            radius: 64
            opacity: 0.5
            transparentBorder: true
        }
    }

    ColumnLayout {
        id: floatingLayout
        anchors.centerIn: parent
        spacing: 12

        Rectangle {
            // indicator drag
            Layout.alignment: Qt.AlignHCenter
            color: Colors.proxy.dividerBorderColor
            width: 48
            height: 4
            radius: 2
        }

        // Icon {
        //     Layout.alignment: Qt.AlignVCenter
        //     size: 24
        //     icon: {
        //         if (AppCentral.scheduleRuntime.currentSubject.icon)
        //             return AppCentral.scheduleRuntime.currentSubject.icon
        //         switch (AppCentral.scheduleRuntime.currentStatus) {
        //         case "free": return "ic_fluent_accessibility_20_regular"
        //         case "break": return "ic_fluent_shifts_activity_20_filled"
        //         case "class": return "ic_fluent_class_20_regular"
        //         case "preparation": return "ic_fluent_hourglass_half_20_regular"
        //         case "activity": return "ic_fluent_alert_20_regular"
        //         default: return "ic_fluent_clock_dismiss_20_regular"
        //         }
        //     }
        // }

        RowLayout {
            Layout.alignment: Qt.AlignCenter
            spacing: 16

            ProgressRing {
                id: rin
                Layout.alignment: Qt.AlignVCenter
                size: 46
                value: AppCentral.scheduleRuntime.currentStatus !== "free" ? AppCentral.scheduleRuntime.progress : 0
                backgroundColor: Colors.proxy.controlAltQuaternaryColor
                primaryColor: root.currentColor
                strokeWidth: 6
                // visible: AppCentral.scheduleRuntime.currentStatus !== "free"
            }

            ColumnLayout {
                spacing: 2
                Layout.alignment: Qt.AlignVCenter
                Title {
                    // font.pixelSize: 26
                    Layout.alignment: Qt.AlignRight
                    text: AppCentral.scheduleRuntime.currentEntry.title
                        || AppCentral.scheduleRuntime.currentSubject.name
                        || (AppCentral.scheduleRuntime.currentStatus === "class"
                          ? qsTr("Class")
                            : AppCentral.scheduleRuntime.currentStatus === "activity"
                          ? qsTr("Activity")
                            : AppCentral.scheduleRuntime.currentStatus === "break"
                          ? qsTr("Take a break")
                            : qsTr("Nothing right now"))
                }
                // 左侧：文字 + 时间
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    spacing: 0
                    opacity: 0.6
                    visible: AppCentral.scheduleRuntime.currentStatus !== "free"


                    AnimatedDigits {
                        id: minute
                        font.pixelSize: 16
                        value: countdown.minute || "00"
                    }
                    Title {
                        font.pixelSize: 16
                        Layout.bottomMargin: font.pixelSize * 0.1
                        text: ":"
                    }
                    AnimatedDigits {
                        font.pixelSize: 16
                        id: second
                        value: (countdown.second + "").padStart(2, "0") || "00"
                    }
                }
            }
        }
    }
}
