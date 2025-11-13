const { LoginSession, EAuthTokenPlatformType, LoginApprover } = require('steam-session');
const SteamTotp = require('steam-totp');

const [,, login, password, sharedSecret, qrUrl] = process.argv;

if (!login || !password || !sharedSecret || !qrUrl) {
    console.error('Usage: node approve_qr.js <login> <password> <shared_secret> <qr_url>');
    process.exit(1);
}

(async () => {
    try {
        const mobileSession = new LoginSession(EAuthTokenPlatformType.MobileApp);
        const code = SteamTotp.generateAuthCode(sharedSecret);

        const startResponse = await mobileSession.startWithCredentials({
            accountName: login,
            password,
            steamGuardCode: code
        });

        if (startResponse.actionRequired) {
            console.log('[!] Additional action required:', startResponse.validActions);
            process.exit(1);
        }

        await new Promise((resolve, reject) => {
            mobileSession.on('authenticated', resolve);
            mobileSession.on('error', reject);
        });

        console.log('[+] Logged in as', mobileSession.steamID.toString());
        const accessToken = mobileSession.accessToken;
        const approver = new LoginApprover(accessToken, sharedSecret);

        console.log('[*] Approving QR session...');

        await approver.approveAuthSession({
            qrChallengeUrl: qrUrl,
            approve: true
        });

        console.log('[✅] QR login approved successfully!');

    } catch (err) {
        console.error('[-] Error:', err);
        process.exit(1);
    }
})();
