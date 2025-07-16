import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Users, CheckCircle, Clock, AlertTriangle, Trash2 } from "lucide-react";

interface User {
  id: number;
  registeredDate: string;
  userId: string;
  status: "active" | "completed" | "error";
  courses: string[];
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [showUserCourses, setShowUserCourses] = useState(false);
  const [showUserLogs, setShowUserLogs] = useState(false);
  const [userLog, setUserLog] = useState<string>("");

  // 실제 API에서 유저 데이터 받아오기
  const [users, setUsers] = useState<User[]>([]);
  useEffect(() => {
    // TODO: 실제 API 엔드포인트로 교체
    fetch("/api/admin/users")
      .then((res) => res.json())
      .then((data) => setUsers(data))
      .catch(() => setUsers([]));
  }, []);

  const totalUsers = users.length;
  const completedUsers = users.filter((user) => user.status === "completed").length;
  const activeUsers = users.filter((user) => user.status === "active").length;
  const errorUsers = users.filter((user) => user.status === "error").length;

  const navigateToMain = () => {
    navigate("/");
  };

  const navigateToChangePassword = () => {
    navigate("/admin/change-password");
  };

  const selectUser = (user: User) => {
    if (selectedUser && selectedUser.id === user.id) {
      setSelectedUser(null);
      setShowUserCourses(false);
    } else {
      setSelectedUser(user);
      setShowUserCourses(true);
      setShowUserLogs(false);
    }
  };

  const showUserStatus = async (user: User) => {
    setSelectedUser(user);
    setShowUserLogs(true);
    setShowUserCourses(false);
    setUserLog("로그 불러오는 중...");
    try {
      const res = await fetch(`/api/admin/user/${user.id}/logs`);
      if (res.ok) {
        const text = await res.text();
        setUserLog(text);
      } else {
        setUserLog("로그 파일 없음");
      }
    } catch {
      setUserLog("로그 불러오기 실패");
    }
  };

  const deleteUser = async (userId: number) => {
    const res = await fetch(`/api/admin/user/${userId}`, { method: "DELETE" });
    if (res.ok) {
      setUsers(users.filter((user) => user.id !== userId));
      if (selectedUser && selectedUser.id === userId) {
        setSelectedUser(null);
        setShowUserCourses(false);
        setShowUserLogs(false);
      }
    } else {
      alert("삭제 실패");
    }
  };

  const getStatusColor = (status: string) => {
    if (status === "active") return "#10B981";
    if (status === "completed") return "#3B82F6";
    if (status === "error") return "#EF4444";
    return "#6B7280";
  };

  const getStatusText = (status: string) => {
    if (status === "active") return "수강중";
    if (status === "completed") return "완료";
    if (status === "error") return "오류";
    return "알 수 없음";
  };

  return (
    <div className="min-h-screen w-full bg-[#F9FAFB]">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-[#E5E7EB] px-6 py-4">
        <div className="flex justify-between items-center max-w-[1200px] mx-auto">
          <h1 className="text-[24px] font-bold text-[#111827] max-sm:text-[20px]">
            관리자 대시보드
          </h1>
          <div className="flex gap-4 max-sm:gap-2">
            <button
              onClick={navigateToChangePassword}
              className="px-4 py-2 text-[#6B7280] hover:text-[#374151] text-[14px] max-sm:px-2 max-sm:text-[12px]"
            >
              비밀번호 변경
            </button>
            <button
              onClick={navigateToMain}
              className="px-4 py-2 bg-[#6B7280] text-white rounded-[8px] hover:bg-[#4B5563] text-[14px] max-sm:px-2 max-sm:text-[12px]"
            >
              로그아웃
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-[1200px] mx-auto p-6 max-sm:p-4">
        {/* Statistics Cards */}
        <div className="grid grid-cols-4 gap-6 mb-8 max-lg:grid-cols-2 max-sm:grid-cols-1">
          <div className="bg-white rounded-[12px] shadow-sm border border-[#E5E7EB] p-6 max-sm:p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[14px] font-medium text-[#6B7280] mb-1">
                  총 등록 유저
                </p>
                <p className="text-[32px] font-bold text-[#111827] max-sm:text-[24px]">
                  {totalUsers.toLocaleString()}
                </p>
              </div>
              <div className="w-12 h-12 bg-[#EBF8FF] rounded-[8px] flex items-center justify-center max-sm:w-10 max-sm:h-10">
                <Users className="w-6 h-6 text-[#3B82F6] max-sm:w-5 max-sm:h-5" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-[12px] shadow-sm border border-[#E5E7EB] p-6 max-sm:p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[14px] font-medium text-[#6B7280] mb-1">
                  수강 완료
                </p>
                <p className="text-[32px] font-bold text-[#10B981] max-sm:text-[24px]">
                  {completedUsers.toLocaleString()}
                </p>
              </div>
              <div className="w-12 h-12 bg-[#ECFDF5] rounded-[8px] flex items-center justify-center max-sm:w-10 max-sm:h-10">
                <CheckCircle className="w-6 h-6 text-[#10B981] max-sm:w-5 max-sm:h-5" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-[12px] shadow-sm border border-[#E5E7EB] p-6 max-sm:p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[14px] font-medium text-[#6B7280] mb-1">
                  수강 중
                </p>
                <p className="text-[32px] font-bold text-[#F59E0B] max-sm:text-[24px]">
                  {activeUsers.toLocaleString()}
                </p>
              </div>
              <div className="w-12 h-12 bg-[#FFFBEB] rounded-[8px] flex items-center justify-center max-sm:w-10 max-sm:h-10">
                <Clock className="w-6 h-6 text-[#F59E0B] max-sm:w-5 max-sm:h-5" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-[12px] shadow-sm border border-[#E5E7EB] p-6 max-sm:p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[14px] font-medium text-[#6B7280] mb-1">
                  오류 발생
                </p>
                <p className="text-[32px] font-bold text-[#EF4444] max-sm:text-[24px]">
                  {errorUsers.toLocaleString()}
                </p>
              </div>
              <div className="w-12 h-12 bg-[#FEF2F2] rounded-[8px] flex items-center justify-center max-sm:w-10 max-sm:h-10">
                <AlertTriangle className="w-6 h-6 text-[#EF4444] max-sm:w-5 max-sm:h-5" />
              </div>
            </div>
          </div>
        </div>

        {/* User Management Table */}
        <div className="bg-white rounded-[12px] shadow-sm border border-[#E5E7EB]">
          <div className="px-6 py-4 border-b border-[#E5E7EB] max-sm:px-4">
            <h2 className="text-[18px] font-semibold text-[#111827] max-sm:text-[16px]">
              유저 관리
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[#F9FAFB]">
                <tr>
                  <th className="px-6 py-3 text-left text-[12px] font-medium text-[#6B7280] uppercase tracking-wider max-sm:px-4">
                    등록일시
                  </th>
                  <th className="px-6 py-3 text-left text-[12px] font-medium text-[#6B7280] uppercase tracking-wider max-sm:px-4">
                    아이디
                  </th>
                  <th className="px-6 py-3 text-left text-[12px] font-medium text-[#6B7280] uppercase tracking-wider max-sm:px-4">
                    상태
                  </th>
                  <th className="px-6 py-3 text-left text-[12px] font-medium text-[#6B7280] uppercase tracking-wider max-sm:px-4">
                    액션
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-[#E5E7EB]">
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-[14px] text-[#111827] max-sm:px-4">
                      {user.registeredDate}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap max-sm:px-4">
                      <button
                        onClick={() => selectUser(user)}
                        className="text-[14px] text-[#3B82F6] hover:text-[#2563EB] cursor-pointer"
                      >
                        {user.userId}
                      </button>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap max-sm:px-4">
                      <button
                        onClick={() => showUserStatus(user)}
                        className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[12px] font-medium cursor-pointer"
                        style={{
                          backgroundColor: getStatusColor(user.status) + "20",
                          color: getStatusColor(user.status),
                        }}
                      >
                        {getStatusText(user.status)}
                      </button>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-[14px] font-medium max-sm:px-4">
                      <button
                        onClick={() => deleteUser(user.id)}
                        className="text-[#EF4444] hover:text-[#DC2626] flex items-center gap-1"
                      >
                        <Trash2 className="w-4 h-4" />
                        삭제
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* User Courses */}
        {selectedUser && showUserCourses && (
          <div className="mt-6 bg-white rounded-[12px] shadow-sm border border-[#E5E7EB]">
            <div className="px-6 py-4 border-b border-[#E5E7EB] max-sm:px-4">
              <h3 className="text-[16px] font-semibold text-[#111827] max-sm:text-[14px]">
                {selectedUser.userId}의 수강 강의
              </h3>
            </div>
            <div className="p-6 max-sm:p-4">
              <div className="grid gap-3">
                {selectedUser.courses.map((course, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-3 bg-[#F9FAFB] rounded-[8px]"
                  >
                    <span className="text-[14px] text-[#111827]">{course}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* User Logs */}
        {selectedUser && showUserLogs && (
          <div className="mt-6 bg-white rounded-[12px] shadow-sm border border-[#E5E7EB]">
            <div className="px-6 py-4 border-b border-[#E5E7EB] max-sm:px-4">
              <h3 className="text-[16px] font-semibold text-[#111827] max-sm:text-[14px]">
                {selectedUser.userId}의 최근 로그
              </h3>
            </div>
            <div className="p-6 max-sm:p-4">
              <div className="bg-[#111827] rounded-[8px] p-4 font-mono text-[12px] text-[#10B981] overflow-x-auto max-sm:text-[10px]" style={{whiteSpace: 'pre-wrap'}}>
                {userLog}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
