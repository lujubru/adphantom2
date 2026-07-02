export const formatDate = (dateString) => {
  const date = new Date(dateString);
  return date.toLocaleString();
};

export const formatNumber = (num) => {
  return new Intl.NumberFormat().format(num);
};

export const calculatePercentage = (part, total) => {
  if (total === 0) return 0;
  return ((part / total) * 100).toFixed(1);
};