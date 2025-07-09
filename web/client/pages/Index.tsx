import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import hanyangLogo from "../public/hanyang_logo.png";

export default function Index() {
  const [showPassword, setShowPassword] = useState(false);
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    // 실제 API로 로그인 요청
    try {
      const res = await fetch("/api/user/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId, password }),
      });
      if (res.ok) {
        navigate("/success", { state: { userId } });
      } else {
        const data = await res.json();
        setError(data.message || "로그인 실패");
      }
    } catch {
      setError("서버 오류");
    }
  };

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-[#87CEEB] to-[#4682B4] flex items-center justify-center p-4">
      <div className="bg-white rounded-[20px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] p-8 w-full max-w-[400px] max-sm:p-6">
        <div className="flex flex-col items-center mb-8">
          <img
            src={hanyangLogo}
            alt="한양대학교 로고"
            className="w-[80px] h-[80px] mb-4 rounded-[12px]"
          />
          <h1 className="text-[24px] font-bold text-[#003366] text-center max-sm:text-[20px]">
            한양대학교 포털
          </h1>
        </div>

        <form className="space-y-6" onSubmit={handleSubmit}>
          <div>
            <label className="block text-[14px] font-medium text-[#374151] mb-2">
              아이디
            </label>
            <input
              type="text"
              value={userId}
              onChange={e => setUserId(e.target.value)}
              className="w-full px-4 py-3 border border-[#D1D5DB] rounded-[12px] focus:outline-none focus:ring-2 focus:ring-[#003366] focus:border-transparent text-[16px] max-sm:py-2"
              placeholder="한양대학교 아이디를 입력하세요"
              required
            />
          </div>

          <div>
            <label className="block text-[14px] font-medium text-[#374151] mb-2">
              비밀번호
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-4 py-3 pr-12 border border-[#D1D5DB] rounded-[12px] focus:outline-none focus:ring-2 focus:ring-[#003366] focus:border-transparent text-[16px] max-sm:py-2"
                placeholder="비밀번호를 입력하세요"
                required
              />
              <button
                type="button"
                onClick={togglePasswordVisibility}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#374151] transition-colors duration-200"
              >
                {!showPassword ? (
                  <Eye className="w-5 h-5" />
                ) : (
                  <EyeOff className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>

          {error && <div className="text-red-500 text-sm">{error}</div>}

          <button
            type="submit"
            className="w-full bg-[#003366] text-white py-3 rounded-[12px] font-semibold text-[16px] hover:bg-[#002244] transition-colors duration-200 max-sm:py-2"
          >
            로그인
          </button>
        </form>
      </div>
    </div>
  );
}
