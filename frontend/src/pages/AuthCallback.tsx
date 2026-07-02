import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

export default function AuthCallback() {
  const navigate = useNavigate();
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const params = new URLSearchParams(window.location.search);
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");

    if (accessToken && refreshToken) {
      localStorage.setItem("co_access_token", accessToken);
      localStorage.setItem("co_refresh_token", refreshToken);

      axios.get("/api/onboarding/status", {
        headers: { Authorization: `Bearer ${accessToken}` }
      }).then(r => {
        navigate(r.data.onboarding_complete ? "/invoices" : "/onboarding", { replace: true });
      }).catch(() => {
        navigate("/onboarding", { replace: true });
      });
    } else {
      navigate("/login?error=oauth_failed", { replace: true });
    }
  }, []);

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      height: "100vh",
      fontFamily: "Inter, sans-serif",
      color: "#6B7C8D"
    }}>
      <div style={{ textAlign: "center" }}>
        <div style={{
          width: 40, height: 40,
          border: "3px solid #E0F5EE",
          borderTop: "3px solid #0D9373",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
          margin: "0 auto 1rem"
        }} />
        <p>Входим в систему...</p>
      </div>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
