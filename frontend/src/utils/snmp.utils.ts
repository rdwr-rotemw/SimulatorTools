export const generateRadwareId = (): string => {
  return String(Math.floor(Math.random() * 999999) + 1);
};

export const generateAttackId = (): string => {
  const part1 = Math.floor(Math.random() * 900) + 100; // 100-999
  const currentEpoch = Math.floor(Date.now() / 1000); // Current epoch timestamp in seconds
  const part2 = Math.floor(Math.random() * (currentEpoch + 1)); // 0 to current epoch
  return `${part1}-${String(part2).padStart(10, '0')}`;
};

export const validateIPAddress = (ip: string): boolean => {
  if (!ip || ip.trim() === '') return false;

  // IPv4 check (same as before)
  const ipv4Pattern = /^(\d{1,3}\.){3}\d{1,3}$/;
  if (ipv4Pattern.test(ip)) {
    const parts = ip.split('.');
    return parts.every(part => {
      const num = parseInt(part, 10);
      return num >= 0 && num <= 255;
    });
  }

  // IPv6 pattern (covers full, compressed, and IPv4-mapped forms)
  // Allow optional zone index like '%eth0' or '%1' at the end
  const ipv6Pattern = new RegExp(
    '^(' +
      '(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}|' + // 1:2:3:4:5:6:7:8
      '(?:[A-Fa-f0-9]{1,4}:){1,7}:|' +               // 1::                              1:2:3:4:5:6:7::
      ':(?::[A-Fa-f0-9]{1,4}){1,7}|' +               // ::2:3:4:5:6:7:8
      '(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}|' +
      '(?:[A-Fa-f0-9]{1,4}:){1,5}(?::[A-Fa-f0-9]{1,4}){1,2}|' +
      '(?:[A-Fa-f0-9]{1,4}:){1,4}(?::[A-Fa-f0-9]{1,4}){1,3}|' +
      '(?:[A-Fa-f0-9]{1,4}:){1,3}(?::[A-Fa-f0-9]{1,4}){1,4}|' +
      '(?:[A-Fa-f0-9]{1,4}:){1,2}(?::[A-Fa-f0-9]{1,4}){1,5}|' +
      '[A-Fa-f0-9]{1,4}:(?::[A-Fa-f0-9]{1,4}){1,6}|' +
      // IPv4-mapped IPv6 and ::ffff:0:0/96 style
      '::(?:ffff:(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)(?:\\.(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)){3})|' +
      '(?:[A-Fa-f0-9]{1,4}:){1,4}:(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)(?:\\.(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)){3}' +
    ')(?:%[0-9A-Za-z]+)?$'
  );

  return ipv6Pattern.test(ip);
};

export const validatePort = (port: string): boolean => {
  const portNum = parseInt(port, 10);
  return !isNaN(portNum) && portNum >= 0 && portNum <= 65535;
};

export const validatePositiveInteger = (value: string): boolean => {
  const num = parseInt(value, 10);
  return !isNaN(num) && num >= 0;
};

export const isValidSamplesFormat = (samples: string): boolean => {
  // Format: "0-0-0" (three numbers separated by dashes)
  const pattern = /^\d+-\d+-\d+$/;
  return pattern.test(samples);
};
