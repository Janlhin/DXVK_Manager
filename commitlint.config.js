// 唯一被精确豁免的历史提交：#8 中 dependabot 生成的 Pillow 版本 bump
// （be99e6b81f40fd4de8d39993651c37cdf7405abf）。其正文含一条 107 字符链接行，
// 提交已在远端、不可改写；这里仅对这一条报文做整文等值豁免，
// 其余提交仍受 body-max-line-length=100 的 error 级约束。
const EXEMPTED_MESSAGE = `build(deps): update pillow requirement from >=9.0 to >=13.0.0

Updates the requirements on [pillow](https://github.com/python-pillow/Pillow) to permit the latest version.
- [Release notes](https://github.com/python-pillow/Pillow/releases)
- [Changelog](https://github.com/python-pillow/Pillow/blob/main/CHANGES.rst)
- [Commits](https://github.com/python-pillow/Pillow/compare/9.0.0...13.0.0)

---
updated-dependencies:
- dependency-name: pillow
  dependency-version: 13.0.0
  dependency-type: direct:production
...

Signed-off-by: dependabot[bot] <support@github.com>`;

export default {
  extends: ["@commitlint/config-conventional"],
  ignores: [(commit) => commit.trimEnd() === EXEMPTED_MESSAGE.trimEnd()],
  rules: {
    "body-max-line-length": [2, "always", 100]
  }
};
