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
  const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
  if (!ipPattern.test(ip)) return false;

  const parts = ip.split('.');
  return parts.every(part => {
    const num = parseInt(part, 10);
    return num >= 0 && num <= 255;
  });
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

