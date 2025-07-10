import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";

export default function ChangePassword() {
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const navigate = useNavigate();

  const toggleCurrentPasswordVisibility = () => {
    setShowCurrentPassword(!showCurrentPassword);
  };

  const toggleNewPasswordVisibility = () => {
    setShowNewPassword(!showNewPassword);
  };

  const toggleConfirmPasswordVisibility = () => {
    setShowConfirmPassword(!showConfirmPassword);
  };

  const navigateToAdminLogin = () => {
    navigate("/admin/login");
  };

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-[#F3F4F6] to-[#E5E7EB] flex items-center justify-center p-4">
      <div className="bg-white rounded-[20px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] p-8 w-full max-w-[400px] max-sm:p-6">
        <div className="flex flex-col items-center mb-8">
          <h1 className="text-[24px] font-bold text-[#374151] text-center max-sm:text-[20px]">
            비밀번호 변경
          </h1>
        </div>

        <form className="space-y-6">
          <div>
            <label className="block text-[14px] font-medium text-[#374151] mb-2">
              현재 비밀번호
            </label>
            <div className="relative">
              <input
                type={showCurrentPassword ? "text" : "password"}
                className="w-full px-4 py-3 pr-12 border border-[#D1D5DB] rounded-[12px] focus:outline-none focus:ring-2 focus:ring-[#6B7280] focus:border-transparent text-[16px] max-sm:py-2"
                placeholder="현재 비밀번호를 입력하세요"
              />
              <button
                type="button"
                onClick={toggleCurrentPasswordVisibility}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#374151] transition-colors duration-200"
              >
                {!showCurrentPassword ? (
                  <Eye className="w-5 h-5" />
                ) : (
                  <EyeOff className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-[14px] font-medium text-[#374151] mb-2">
              새 비밀번호
            </label>
            <div className="relative">
              <input
                type={showNewPassword ? "text" : "password"}
                className="w-full px-4 py-3 pr-12 border border-[#D1D5DB] rounded-[12px] focus:outline-none focus:ring-2 focus:ring-[#6B7280] focus:border-transparent text-[16px] max-sm:py-2"
                placeholder="새 비밀번호를 입력하세요"
              />
              <button
                type="button"
                onClick={toggleNewPasswordVisibility}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#374151] transition-colors duration-200"
              >
                {!showNewPassword ? (
                  <Eye className="w-5 h-5" />
                ) : (
                  <EyeOff className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-[14px] font-medium text-[#374151] mb-2">
              새 비밀번호 확인
            </label>
            <div className="relative">
              <input
                type={showConfirmPassword ? "text" : "password"}
                className="w-full px-4 py-3 pr-12 border border-[#D1D5DB] rounded-[12px] focus:outline-none focus:ring-2 focus:ring-[#6B7280] focus:border-transparent text-[16px] max-sm:py-2"
                placeholder="새 비밀번호를 다시 입력하세요"
              />
              <button
                type="button"
                onClick={toggleConfirmPasswordVisibility}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#374151] transition-colors duration-200"
              >
                {!showConfirmPassword ? (
                  <Eye className="w-5 h-5" />
                ) : (
                  <EyeOff className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="w-full bg-[#6B7280] text-white py-3 rounded-[12px] font-semibold text-[16px] hover:bg-[#4B5563] transition-colors duration-200 max-sm:py-2"
          >
            비밀번호 변경
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={navigateToAdminLogin}
            className="text-[#6B7280] text-[14px] hover:underline"
          >
            ← 관리자 로그인으로
          </button>
        </div>
      </div>
    </div>
  );
}
