import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI


FluentPage {
    id: root
    title: qsTr("集控")

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4

        Text {
            typography: Typography.BodyStrong
            text: qsTr("集控")
        }

        SettingCard {
            Layout.fillWidth: true
            icon.name: "ic_fluent_cloud_arrow_down_20_regular"
            title: qsTr("集控地址")
            description: qsTr("填写 GitHub Pages 上的集控清单地址（manifest.json）；留空时不会拉取任何集控内容。")

            TextField {
                id: manifestUrlField
                Layout.fillWidth: true
                placeholderText: "https://example.github.io/repository/manifest.json"
                Component.onCompleted: text = AppCentral.centralControl.manifestUrl
                onEditingFinished: {
                    text = text.trim()
                    AppCentral.centralControl.setManifestUrl(text)
                }
            }
        }

        SettingCard {
            Layout.fillWidth: true
            icon.name: "ic_fluent_arrow_sync_20_regular"
            title: qsTr("拉取方式")
            description: qsTr("手动模式仅在点击检查按钮时拉取；自动模式会在启动后和指定间隔自动拉取。")

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                Switch {
                    id: autoFetchSwitch
                    text: qsTr("自动拉取集控内容")
                    checked: AppCentral.centralControl.autoFetchEnabled
                    onToggled: AppCentral.centralControl.setAutoFetchEnabled(checked)
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: autoFetchSwitch.checked
                    enabled: autoFetchSwitch.checked
                    spacing: 8

                    Text {
                        text: qsTr("检查间隔")
                    }

                    SpinBox {
                        id: autoFetchInterval
                        property bool initialized: false
                        from: 1
                        to: 1440
                        value: AppCentral.centralControl.autoFetchIntervalMinutes
                        editable: true
                        onValueChanged: {
                            if (initialized)
                                AppCentral.centralControl.setAutoFetchIntervalMinutes(value)
                        }
                        Component.onCompleted: initialized = true
                    }

                    Text {
                        text: qsTr("分钟")
                        color: Colors.proxy.textSecondaryColor
                    }

                    Item { Layout.fillWidth: true }
                }
            }
        }

        SettingCard {
            Layout.fillWidth: true
            icon.name: "ic_fluent_power_20_regular"
            title: qsTr("远程电源命令")
            description: qsTr("仅在本机明确启用后，才接受集控下发的重启、关机、休眠或睡眠命令；拉取到有效命令后会立即执行。")

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                Switch {
                    text: qsTr("允许接收远程电源命令")
                    checked: AppCentral.centralControl.allowRemotePowerCommands
                    onToggled: AppCentral.centralControl.setAllowRemotePowerCommands(checked)
                }
            }
        }

        SettingCard {
            Layout.fillWidth: true
            icon.name: "ic_fluent_calendar_arrow_down_20_regular"
            title: qsTr("接收集控内容")
            description: qsTr("下载并校验多个课程表；仅恰好一份课表声明 yes.id=1 时自动切换，否则只保存为可选项。")

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    Layout.fillWidth: true
                    color: Colors.proxy.textSecondaryColor
                    text: AppCentral.centralControl.statusText
                    wrapMode: Text.WordWrap
                }

                Text {
                    visible: AppCentral.centralControl.lastAppliedName !== ""
                    color: Colors.proxy.textSecondaryColor
                    text: qsTr("已自动切换的集控课程表：%1（策略版本：%2）")
                        .arg(AppCentral.centralControl.lastAppliedName)
                        .arg(AppCentral.centralControl.lastPolicyVersion)
                    wrapMode: Text.WordWrap
                }

                Text {
                    visible: AppCentral.centralControl.lastAnnouncementCount > 0
                    color: Colors.proxy.textSecondaryColor
                    text: qsTr("本次已处理 %1 条一次性公告命令。")
                        .arg(AppCentral.centralControl.lastAnnouncementCount)
                }

                Text {
                    visible: AppCentral.centralControl.centralSchedules.length > 0
                    text: qsTr("已同步的集控课程表")
                    typography: Typography.BodyStrong
                }

                Repeater {
                    model: AppCentral.centralControl.centralSchedules

                    delegate: Frame {
                        required property var modelData
                        readonly property var schedule: modelData
                        Layout.fillWidth: true

                        RowLayout {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            spacing: 8

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2

                                Text {
                                    Layout.fillWidth: true
                                    text: schedule.name
                                    typography: Typography.BodyStrong
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: qsTr("标识：%1").arg(schedule.id)
                                    color: Colors.proxy.textSecondaryColor
                                    typography: Typography.Caption
                                }
                            }

                            Button {
                                text: qsTr("应用")
                                onClicked: AppCentral.centralControl.applyCentralSchedule(schedule.id)
                            }
                        }
                    }
                }

                Text {
                    visible: AppCentral.centralControl.lastMatchStatus !== ""
                    Layout.fillWidth: true
                    text: qsTr("yes.id 匹配结果：%1").arg(AppCentral.centralControl.lastMatchStatus)
                    color: Colors.proxy.textSecondaryColor
                    wrapMode: Text.WordWrap
                }

                Button {
                    text: AppCentral.centralControl.syncing
                          ? qsTr("正在检查…")
                          : qsTr("检查并同步集控内容")
                    enabled: !AppCentral.centralControl.syncing
                    onClicked: AppCentral.centralControl.fetchAndApplySchedule()
                }
            }
        }
    }
}
