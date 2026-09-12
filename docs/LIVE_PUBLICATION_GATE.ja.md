# 公開LIVEリリースゲート

`/connectome` を公開可能とする条件は、実際に配信される同一runtime releaseについて以下をすべて満たすことです。

- Vercelは固定名の共有LIVEを1つだけ使用し、視聴者数でモデルprocessを増やさない。
- 主表示はFightingICE v7.1公式`ScreenData`。疑似描画をLIVEゲーム画面として代用しない。
- 画面pixelはspectator-onlyで、MaleCNSのaction選択・学習への入力は禁止する。
- 同じdecision windowで、実sensory body drive、recurrent spike、実motor body contribution、7 action-group、selected action、実FightingICE x/y/HP/actionを対応付ける。
- 神経解剖表示には公式公開MaleCNS v1.0 SWC contextと実body-ID annotationを使う。top-spiking sampleによるregion表示を全ニューロン活動図や機能同定と表現しない。
- ハエ身体表示は補助表示とし、実action/facing/x/y/hitのみから姿勢・移動を表す。装飾移動を観測された生物運動として扱わない。
- スマホでは公式戦闘画面を最上部に置く1カラム構成とし、320 CSS px幅で横スクロールを要求しない。
- warming/error時に偽の戦闘・frame・神経活動・解剖位置を生成しない。
- GitHub candidate学習はVercel served stateと分離し、別promotion gateなしに自動公開しない。

production smokeは公式ScreenDataまたは同期神経side-channelが欠落した場合に失敗しなければなりません。
