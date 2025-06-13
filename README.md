# LibreDomains - 自由域名分发服务

LibreDomains 是一个开源的二级域名分发服务，允许用户通过 GitHub Pull Request 来申请和管理二级域名。

## 快速导航

- 🚀 [开始申请域名](#申请域名) - 立即申请你的免费二级域名
- 📖 [用户指南](docs/user-guide.md) - 详细的使用教程和常见问题
- 👥 [管理员指南](docs/admin-guide.md) - 管理员操作指南
- 🔧 [技术文档](docs/technical-doc.md) - 技术实现和 API 参考
- 📊 [项目概览](docs/implementation-summary.md) - 功能清单和架构说明

## 可用域名

目前，本项目提供以下域名：

| 域名 | 状态 | 描述 |
|------|------|------|
| ciao.su | ✅ 可用 | 主要域名 |
| ciallo.de | ⏸️ 暂停开放 | 备用域名 |

## 申请域名

### 申请步骤

1. Fork 本仓库
2. 在 `domains/[域名]/` 目录下创建一个以你想要申请的子域名命名的 JSON 文件
   - 例如: `domains/ciao.su/mysubdomain.json`
3. 按照下面的格式填写 JSON 文件
4. 提交 Pull Request
5. 等待自动检查和审核
6. Pull Request 被合并后，你的域名记录将在几分钟内生效

### JSON 格式

```json
{
  "owner": {
    "name": "你的名字",
    "github": "你的GitHub用户名",
    "email": "你的邮箱"
  },
  "records": [
    {
      "type": "A",
      "name": "@",
      "content": "xxx.xxx.xxx.xxx",
      "ttl": 3600,
      "proxied": true
    },
    {
      "type": "CNAME",
      "name": "www",
      "content": "xxx.com",
      "ttl": 3600,
      "proxied": true
    }
  ]
}
```

### 支持的 DNS 记录类型

- `A` - IPv4 地址
- `AAAA` - IPv6 地址
- `CNAME` - 别名
- `TXT` - 文本记录
- `MX` - 邮件交换记录

### 规则

1. 子域名必须由小写字母、数字和连字符组成
2. 子域名长度在 2-63 个字符之间
3. 子域名不能以连字符开头或结尾
4. 一个 GitHub 用户最多可以申请 3 个子域名
5. 每个子域名最多可以有 10 个 DNS 记录
6. **不允许申请以下保留的子域名**（这些子域名由系统保留，用于特定功能或管理目的）:
   - **根域名**: `@` (根域名由管理员控制)
   - **系统保留**: `www`, `mail`, `email`, `webmail`, `ns`, `dns`
   - **服务保留**: `api`, `cdn`, `ftp`, `sftp`
   - **管理保留**: `admin`, `panel`, `dashboard`, `control`
   - **开发保留**: `dev`, `test`, `staging`, `demo`
   - **内容保留**: `blog`, `forum`, `wiki`, `docs`, `tv`
   - **应用保留**: `app`, `mobile`, `static`, `assets`

## 管理域名

成功创建你的域名后，若要更新记录:

1. 编辑你之前创建的 JSON 文件
2. 提交新的 Pull Request
3. 等待自动检查和审核
4. Pull Request 被合并后，更新将在几分钟内生效

## 文档

更多详细信息请参考以下文档：

- **[用户指南](docs/user-guide.md)** - 详细的域名申请和管理教程
- **[管理员指南](docs/admin-guide.md)** - 管理员操作和维护指南
- **[技术文档](docs/technical-doc.md)** - 项目技术架构和实现细节
- **[项目实施总结](docs/implementation-summary.md)** - 项目功能清单和架构概览

## 贡献代码

欢迎提交 Pull Request 来改进本项目！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

## 技术实现

- Python 脚本处理域名验证和部署
- GitHub Actions 用于自动化 PR 检查和部署
- Cloudflare API 进行 DNS 记录管理

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件
