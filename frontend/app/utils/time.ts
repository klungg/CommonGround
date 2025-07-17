/**
 * Formats a message timestamp.
 * @param timestamp The date to format.
 * @returns The formatted time string.
 */
export const formatMessageTime = (timestamp: Date) => {
  const now = new Date();
  const time = new Date(timestamp);
  
  // Format the time to 12-hour format
  const timeString = time.toLocaleString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  });

  // Check if it is today
  const isToday = time.toDateString() === now.toDateString();
  if (isToday) {
    return timeString;
  }

  // Check if it is this week
  const startOfWeek = new Date(now);
  startOfWeek.setDate(now.getDate() - now.getDay());
  startOfWeek.setHours(0, 0, 0, 0);
  
  const endOfWeek = new Date(startOfWeek);
  endOfWeek.setDate(startOfWeek.getDate() + 6);
  endOfWeek.setHours(23, 59, 59, 999);

  if (time >= startOfWeek && time <= endOfWeek) {
    const weekday = time.toLocaleString('en-US', { weekday: 'short' });
    return `${weekday} ${timeString}`;
  }

  // Check if it is this year
  const isThisYear = time.getFullYear() === now.getFullYear();
  if (isThisYear) {
    const month = time.getMonth() + 1;
    const date = time.getDate();
    return `${month}-${date} ${timeString}`;
  }

  // 不是今年
  return `${time.getFullYear()}-${time.getMonth() + 1}-${time.getDate()} ${timeString}`;
}; 
