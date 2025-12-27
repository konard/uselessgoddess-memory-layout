#include <windows.h>
#include <winternl.h>
#include <tlhelp32.h>
#include <tchar.h>
#include <iostream>
#include <string>
#include <vector>
#include <functional>
#include "api.h"

// bool EnableDebugPrivilege() {
//     HANDLE hToken;
//     if (!OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, &hToken)) {
//         return false;
//     }

//     TOKEN_PRIVILEGES tp;
//     tp.PrivilegeCount = 1;
//     if (!LookupPrivilegeValue(NULL, SE_DEBUG_NAME, &tp.Privileges[0].Luid)) {
//         CloseHandle(hToken);
//         return false;
//     }

//     tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;
//     if (!AdjustTokenPrivileges(hToken, FALSE, &tp, sizeof(tp), NULL, NULL)) {
//         CloseHandle(hToken);
//         return false;
//     }

//     CloseHandle(hToken);
//     return true;
// }

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
    std::vector<BYTE> buffer(0x10000);
    while (true) {
        DWORD needed;
        NTSTATUS status = NtQuerySystemInformation(SystemHandleInformation, buffer.data(), (ULONG)buffer.size(), &needed);
        if (status == STATUS_INFO_LENGTH_MISMATCH) {
            buffer.resize(needed + 0x1000);
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
    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_DUP_HANDLE, FALSE, pid);
    if (hProcess == NULL) {
        return false;
    }

    bool closed = !EnumHandles(pid, [&hProcess, &closed](SYSTEM_HANDLE_TABLE_ENTRY_INFO handle) {
        // duplicate the handle to our process so we can query it
        HANDLE hDuplicate;
        if (!DuplicateHandle(hProcess, (HANDLE)handle.HandleValue, GetCurrentProcess(), &hDuplicate, 0, FALSE, DUPLICATE_SAME_ACCESS)) {
            return true;
        }

        // get the name of the object
        ULONG returnLength;
        if (NtQueryObject(hDuplicate, ObjectNameInformation, NULL, 0, &returnLength) != STATUS_INFO_LENGTH_MISMATCH) {
            CloseHandle(hDuplicate);
            return true;
        }

        std::vector<BYTE> buffer(returnLength);
        if (NtQueryObject(hDuplicate, ObjectNameInformation, buffer.data(), returnLength, &returnLength) != STATUS_SUCCESS) {
            CloseHandle(hDuplicate);
            return true;
        }

        // check if this is the one
        POBJECT_NAME_INFORMATION name = (POBJECT_NAME_INFORMATION)buffer.data();
        std::wstring nameStr(name->Name.Buffer, name->Name.Length / sizeof(WCHAR));

        if (nameStr.find(L"csgo_singleton_mutex") == std::wstring::npos) {
            CloseHandle(hDuplicate);
            return true;
        }

        // close the duplicated handle
        CloseHandle(hDuplicate);

        // duplicate again but this time steal it and close it
        DuplicateHandle(hProcess, (HANDLE)handle.HandleValue, GetCurrentProcess(), &hDuplicate, 0, FALSE, DUPLICATE_CLOSE_SOURCE);
        CloseHandle(hDuplicate);

#ifndef LIB_CS2CH
        std::wcout << L"Closed handle: " << handle.HandleValue << std::endl;
#endif

        return false;
    });

    CloseHandle(hProcess);

    return closed;
}

bool CloseAllMutexes() {
    bool closed = false;

    EnumProcessesByName(TEXT("cs2.exe"), [&closed](DWORD pid) {
#ifndef LIB_CS2CH
        std::wcout << L"found cs2.exe with pid: " << pid << std::endl;
#endif
        closed |= CloseMutexForProcess(pid);

        return true;
    });

    return closed;
}

DWORD __stdcall CloseMutexForProcessExport(DWORD pid) {
#ifdef LIB_CS2CH
    #pragma comment(linker, "/EXPORT:CloseMutexForProcess=" __FUNCDNAME__)
#endif

    return CloseMutexForProcess(pid) ? 0 : 1;
}

DWORD __stdcall CloseAllMutexesExport() {
#ifdef LIB_CS2CH
    #pragma comment(linker, "/EXPORT:CloseAllMutexes=" __FUNCDNAME__)
#endif

    return CloseAllMutexes() ? 0 : 1;
}

#ifndef LIB_CS2CH
int main(int, char**) {
    // not needed
    // EnableDebugPrivilege();
    return CloseAllMutexes() ? 0 : 1;
}
#endif