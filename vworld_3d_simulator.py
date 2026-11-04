
import streamlit as st
import streamlit.components.v1 as components
from urllib.parse import quote

st.set_page_config(
    page_title="서울 3D 운전 교실",
    page_icon="🚗",
    layout="wide"
)

st.title("🚗 서울 3D 운전 교실")
st.subheader("브이월드 3D 지도 진단")

st.info(
    "현재는 지도 연결을 먼저 확인하는 단계입니다. "
    "자동차 주행 기능은 지도 확인 후 복구할 예정입니다."
)

# 1. API 키 확인
try:
    api_key = str(st.secrets["VWORLD_API_KEY"]).strip()
except Exception:
    st.error(
        "Streamlit Secrets에서 VWORLD_API_KEY를 읽지 못했습니다."
    )
    st.stop()

if not api_key:
    st.error("VWORLD_API_KEY가 비어 있습니다.")
    st.stop()

encoded_key = quote(api_key, safe="")

# 2. 지도 HTML
html = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #e9eef3;
    font-family: Arial, sans-serif;
}

#status {
    padding: 12px;
    background: #17324d;
    color: white;
    font-size: 14px;
}

#map {
    width: 100%;
    height: 650px;
    background: #e9eef3;
}

#error {
    display: none;
    margin: 8px;
    padding: 12px;
    color: white;
    background: #8b2424;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-size: 13px;
}
</style>

<script
    src="https://map.vworld.kr/js/webglMapInit.js.do?version=3.0&apiKey=__VWORLD_KEY__"
    onerror="window.vworldScriptLoadFailed = true;">
</script>

</head>

<body>

<div id="status">브이월드 라이브러리 확인 중...</div>
<div id="error"></div>
<div id="map"></div>

<script>
(function () {

    const status = document.getElementById("status");
    const errorBox = document.getElementById("error");

    function showError(message) {
        status.textContent = "지도 초기화 실패";
        errorBox.style.display = "block";
        errorBox.textContent = message;
        console.error("[VWorld 진단]", message);
    }

    function getAuthInfo() {
        return {
            valid: window.vworldIsValid,
            message: window.vworldErrMsg,
            keyPresent: Boolean(window.vworldApiKey),
            keyLength: window.vworldApiKey
                ? window.vworldApiKey.length
                : 0
        };
    }

    window.addEventListener("error", function (event) {
        console.error(
            "[JavaScript 오류]",
            event.message,
            event.filename,
            event.lineno
        );
    });

    window.addEventListener("unhandledrejection", function (event) {
        console.error("[비동기 오류]", event.reason);
    });

    // 브이월드 라이브러리 로딩 확인
    if (window.vworldScriptLoadFailed) {
        showError(
            "브이월드 스크립트 요청 자체가 실패했습니다.\n" +
            "브라우저 Console과 Network 탭을 확인해야 합니다."
        );
        return;
    }

    // 인증 응답 확인
    const auth = getAuthInfo();

    console.log("[VWorld 인증 진단]", auth);

    if (auth.valid === "false" || auth.valid === false) {
        showError(
            "브이월드 인증 실패\n\n" +
            "인증 상태: " + auth.valid + "\n" +
            "인증 메시지: " + (auth.message || "메시지 없음") + "\n" +
            "전달된 키 존재 여부: " + auth.keyPresent + "\n" +
            "전달된 키 길이: " + auth.keyLength + "\n\n" +
            "API 키 값은 보안상 표시하지 않습니다."
        );
        return;
    }

    if (!window.vw) {
        showError(
            "브이월드 라이브러리 객체(window.vw)를 찾지 못했습니다.\n\n" +
            "인증 상태: " + auth.valid + "\n" +
            "인증 메시지: " + (auth.message || "메시지 없음") + "\n" +
            "키 존재 여부: " + auth.keyPresent + "\n" +
            "키 길이: " + auth.keyLength
        );
        return;
    }

    try {

        status.textContent = "3D 지도 초기화 중...";

        const map = new vw.Map();

        const options = {
            mapId: "map",
            initPosition: new vw.CameraPosition(
                new vw.CoordZ(126.9780, 37.5665, 1800),
                new vw.Direction(0, -45, 0)
            ),
            logo: true,
            navigation: true
        };

        map.setOption(options);

        // 지도 초기화 콜백
        vw.ws3dInitCallBack = function () {
            try {
                if (typeof ws3d === "undefined" || !ws3d.viewer) {
                    showError(
                        "지도 콜백 실행 후에도 Viewer를 찾지 못했습니다."
                    );
                    return;
                }

                status.textContent =
                    "3D 지도 초기화 완료. 서울시청 주변을 확인해 보세요.";

                console.log("[VWorld] Viewer 준비 완료");

            } catch (error) {
                showError(
                    "초기화 콜백 오류: " + error.message
                );
            }
        };

        map.start();

        status.textContent = "지도 시작 요청 완료. 로딩을 기다리는 중...";

        setTimeout(function () {
            if (
                status.textContent.indexOf("지도 시작 요청 완료") !== -1
            ) {
                showError(
                    "지도 시작 요청 후 25초가 지났지만 초기화 콜백이 실행되지 않았습니다.\n\n" +
                    "브이월드 지도 데이터 요청 또는 초기화 과정에서 문제가 발생했을 수 있습니다."
                );
            }
        }, 25000);

    } catch (error) {
        showError(
            "지도 초기화 과정에서 오류가 발생했습니다.\n" +
            error.message
        );
    }

})();
</script>

</body>
</html>
"""

html = html.replace("__VWORLD_KEY__", encoded_key)

components.html(
    html,
    height=700,
    scrolling=False
)
