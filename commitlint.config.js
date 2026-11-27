export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // dependabot 自动生成的正文带完整链接，单行可能超过 100 字符；
    // 这类提交已在远端、不能改写，正文换行长度不做强校验（type/subject 等结构规则保留）。
    "body-max-line-length": [0, "always"]
  }
};
