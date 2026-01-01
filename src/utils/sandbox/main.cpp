#include <windows.h>
#include <winternl.h>
#include <tlhelp32.h>
#include <tchar.h>
#include <iostream>
#include <string>
#include <vector>
#include <functional>
#include "api.h"

#pragma comment(lib, "advapi32.lib")

// Глобальные указатели на функции
PNT_QUERY_SYSTEM_INFORMATION pNtQuerySystemInformation = nullptr;
PNT_QUERY_OBJECT pNtQueryObject = nullptr;

// Инициализация Native API
bool InitNativeApi() {
    HMODULE hNtdll = GetModuleHandle(TEXT("ntdll.dll"));
    if (!hNtdll) return false;

    pNtQuerySystemInformation = (PNT_QUERY_SYSTEM_INFORMATION)GetProcAddress(hNtdll, "NtQuerySystemInformation");
    pNtQueryObject = (PNT_QUERY_OBJECT)GetProcAddress(hNtdll, "NtQueryObject");

    return (pNtQuerySystemInformation && pNtQueryObject);
}

bool EnableDebugPrivilege() {
    HANDLE hToken;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, &hToken)) {
        return false;
    }

    TOKEN_PRIVILEGES tp;
    tp.PrivilegeCount = 1;
    if (!LookupPrivilegeValue(NULL, SE_DEBUG_NAME, &tp.Privileges[0].Luid)) {
        CloseHandle(hToken);
        return false;
    }

    tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;
    if (!AdjustTokenPrivileges(hToken, FALSE, &tp, sizeof(tp), NULL, NULL)) {
        CloseHandle(hToken);
        return false;
    }

    CloseHandle(hToken);
    return true;
}

bool EnumProcessesByName(const TCHAR* processName, std::function<bool(DWORD)> callback) {
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) {
        return false;
    }

    PROCESSENTRY32 pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32);
    bool success = true;
    if (!Process32First(hSnapshot, &pe32)) {
        CloseHandle(hSnapshot);
        return false;
    }

    do {
        if (_tcsicmp(pe32.szExeFile, processName) == 0) {
            if (!callback(pe32.th32ProcessID)) {
                success = false;
                break;
            }
        }
    } while (Process32Next(hSnapshot, &pe32));

    CloseHandle(hSnapshot);
    return success;
}

bool EnumHandles(DWORD processId, std::function<bool(SYSTEM_HANDLE_TABLE_ENTRY_INFO)> callback) {
    if (!pNtQuerySystemInformation) return false;

    std::vector<BYTE> buffer(0x100000); // 1MB buffer
    while (true) {
        ULONG needed = 0;
        NTSTATUS status = pNtQuerySystemInformation(SystemHandleInformation, buffer.data(), (ULONG)buffer.size(), &needed);
        if (status == STATUS_INFO_LENGTH_MISMATCH) {
            buffer.resize(needed + 0x2000);
        } else if (status == STATUS_SUCCESS) {
            break;
        } else {
            return false;
        }
    }

    PSYSTEM_HANDLE_INFORMATION handles = (PSYSTEM_HANDLE_INFORMATION)buffer.data();
    for (ULONG i = 0; i < handles->NumberOfHandles; i++) {
        SYSTEM_HANDLE_TABLE_ENTRY_INFO handle = handles->Handles[i];
        if (handle.UniqueProcessId != processId) {
            continue;
        }
        if (!callback(handle)) {
            return false;
        }
    }

    return true;
}

bool CloseMutexForProcess(DWORD pid) {
    if (!pNtQueryObject) return false;

    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_DUP_HANDLE, FALSE, pid);
    if (hProcess == NULL) {
        // Если не удалось открыть, возможно, нужны права админа
        return false;
    }

    bool result = false;

    EnumHandles(pid, [&hProcess, &result, &pid](SYSTEM_HANDLE_TABLE_ENTRY_INFO handle) {
        HANDLE hDuplicate;
        if (!DuplicateHandle(hProcess, (HANDLE)handle.HandleValue, GetCurrentProcess(), &hDuplicate, 0, FALSE, DUPLICATE_SAME_ACCESS)) {
            return true;
        }

        ULONG returnLength;
        std::vector<BYTE> typeBuffer(0x1000);
        
        // Сначала проверяем тип объекта, чтобы избежать зависаний на пайпах
        if (pNtQueryObject(hDuplicate, ObjectTypeInformation, typeBuffer.data(), (ULONG)typeBuffer.size(), &returnLength) != STATUS_SUCCESS) {
            CloseHandle(hDuplicate);
            return true;
        }

        POBJECT_TYPE_INFORMATION typeInfo = (POBJECT_TYPE_INFORMATION)typeBuffer.data();
        if (typeInfo->TypeName.Buffer) {
            std::wstring typeStr(typeInfo->TypeName.Buffer, typeInfo->TypeName.Length / sizeof(WCHAR));
            if (typeStr != L"Mutant") {
                CloseHandle(hDuplicate);
                return true;
            }
        } else {
            CloseHandle(hDuplicate);
            return true;
        }

        // Теперь безопасно запрашиваем имя
        if (pNtQueryObject(hDuplicate, ObjectNameInformation, NULL, 0, &returnLength) != STATUS_INFO_LENGTH_MISMATCH) {
            CloseHandle(hDuplicate);
            return true;
        }

        std::vector<BYTE> buffer(returnLength);
        if (pNtQueryObject(hDuplicate, ObjectNameInformation, buffer.data(), returnLength, &returnLength) != STATUS_SUCCESS) {
            CloseHandle(hDuplicate);
            return true;
        }

        POBJECT_NAME_INFORMATION name = (POBJECT_NAME_INFORMATION)buffer.data();
        if (name->Name.Buffer) {
            std::wstring nameStr(name->Name.Buffer, name->Name.Length / sizeof(WCHAR));

            if (nameStr.find(L"csgo_singleton_mutex") != std::wstring::npos) {
                CloseHandle(hDuplicate); // Закрываем наш локальный дубликат

                // Принудительно закрываем хендл в целевом процессе
                HANDLE hKill;
                DuplicateHandle(hProcess, (HANDLE)handle.HandleValue, GetCurrentProcess(), &hKill, 0, FALSE, DUPLICATE_CLOSE_SOURCE);
                CloseHandle(hKill);

                #ifndef LIB_CS2CH
                std::wcout << L"[!] Killed Mutex: " << nameStr << L" in PID " << pid << std::endl;
                #endif
                
                result = true;
                return false; // Прерываем перебор для этого процесса
            }
        }

        CloseHandle(hDuplicate);
        return true;
    });

    CloseHandle(hProcess);
    return result;
}

bool CloseAllMutexes() {
    bool closed = false;

    EnumProcessesByName(TEXT("cs2.exe"), [&closed](DWORD pid) {
#ifndef LIB_CS2CH
        std::wcout << L"Checking cs2.exe with pid: " << pid << std::endl;
#endif
        if (CloseMutexForProcess(pid)) {
            closed = true;
        }
        return true;
    });

    return closed;
}

DWORD __stdcall CloseMutexForProcessExport(DWORD pid) {
#ifdef LIB_CS2CH
    #pragma comment(linker, "/EXPORT:CloseMutexForProcess=" __FUNCDNAME__)
#endif
    if (!InitNativeApi() || !EnableDebugPrivilege()) return 0;
    return CloseMutexForProcess(pid) ? 1 : 0;
}

DWORD __stdcall CloseAllMutexesExport() {
#ifdef LIB_CS2CH
    #pragma comment(linker, "/EXPORT:CloseAllMutexes=" __FUNCDNAME__)
#endif
    if (!InitNativeApi() || !EnableDebugPrivilege()) return 0;
    return CloseAllMutexes() ? 1 : 0;
}

#ifndef LIB_CS2CH
int main(int, char**) {
    if (!InitNativeApi()) {
        std::cerr << "Failed to resolve NTAPI functions." << std::endl;
        return 1;
    }

    if (!EnableDebugPrivilege()) {
        std::cerr << "Failed to enable Debug Privilege. Run as Admin." << std::endl;
    }

    bool result = CloseAllMutexes();
    if (!result) {
        std::wcout << L"No mutexes found or killed." << std::endl;
    } else {
        std::wcout << L"Done." << std::endl;
    }
    
    system("pause");
    return result ? 0 : 1;
}
#endif