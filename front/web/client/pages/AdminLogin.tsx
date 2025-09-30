import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";

export default function AdminLogin() {
  const [showAdminPassword, setShowAdminPassword] = useState(false);
  const [adminId, setAdminId] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const toggleAdminPasswordVisibility = () => {
    setShowAdminPassword(!showAdminPassword);
  };

  const navigateToMain = () => {
    navigate("/");
  };

  const navigateToChangePassword = () => {
    navigate("/admin/change-password");
  };

  const handleAdminLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ adminId, adminPassword }),
      });
      const data = await res.json();
      if (res.ok) {
        if (data.change_password) {
          navigate("/admin/change-password");
        } else {
          navigate("/admin/dashboard");
        }
      } else {
        setError(data.message || "로그인 실패");
      }
    } catch {
      setError("서버 오류");
    }
  };

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-[#F3F4F6] to-[#E5E7EB] flex items-center justify-center p-4">
      <div className="bg-white rounded-[20px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] p-8 w-full max-w-[400px] max-sm:p-6">
        <div className="flex flex-col items-center mb-8">
          <h1 className="text-[24px] font-bold text-[#374151] text-center max-sm:text-[20px]">
            관리자 로그인
          </h1>
        </div>

        <form className="space-y-6" onSubmit={handleAdminLogin}>
          <div>
            <label className="block text-[14px] font-medium text-[#374151] mb-2">
              관리자 ID
            </label>
            <input
              type="text"
              value={adminId}
              onChange={e => setAdminId(e.target.value)}
              className="w-full px-4 py-3 border border-[#D1D5DB] rounded-[12px] focus:outline-none focus:ring-2 focus:ring-[#6B7280] focus:border-transparent text-[16px] max-sm:py-2"
              placeholder="관리자 ID를 입력하세요"
              required
            />
          </div>

          <div>
            <label className="block text-[14px] font-medium text-[#374151] mb-2">
              비밀번호
            </label>
            <div className="relative">
              <input
                type={showAdminPassword ? "text" : "password"}
                value={adminPassword}
                onChange={e => setAdminPassword(e.target.value)}
                className="w-full px-4 py-3 pr-12 border border-[#D1D5DB] rounded-[12px] focus:outline-none focus:ring-2 focus:ring-[#6B7280] focus:border-transparent text-[16px] max-sm:py-2"
                placeholder="비밀번호를 입력하세요"
                required
              />
              <button
                type="button"
                onClick={toggleAdminPasswordVisibility}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#374151] transition-colors duration-200"
              >
                {!showAdminPassword ? (
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
            className="w-full bg-[#6B7280] text-white py-3 rounded-[12px] font-semibold text-[16px] hover:bg-[#4B5563] transition-colors duration-200 max-sm:py-2"
          >
            로그인
          </button>
        </form>

        <div className="mt-6 flex justify-between text-[14px]">
          <button
            onClick={navigateToMain}
            className="text-[#6B7280] hover:underline"
          >
            ← 메인으로
          </button>
          <button
            onClick={navigateToChangePassword}
            className="text-[#6B7280] hover:underline"
          >
            비밀번호 변경
          </button>
        </div>
      </div>
    </div>
  );
}
