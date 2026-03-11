# GitHub - ultrazg/xyz: 小宇宙FM API

**URL:** https://github.com/ultrazg/xyz

---

Skip to content
Navigation Menu
Platform
Solutions
Resources
Open Source
Enterprise
Pricing
Sign in
Sign up
ultrazg
/
xyz
Public
Notifications
Fork 30
 Star 183
Code
Issues
6
Pull requests
Actions
Projects
Security
Insights
ultrazg/xyz
 main
2 Branches
19 Tags
Code
Folders and files
Name	Last commit message	Last commit date

Latest commit
ultrazg
chore: README.md
f225e10
 · 
History
107 Commits


constant
	
up 1.9.1
	


doc
	
up 1.9.1
	


handlers
	
feat: 新增「新节目广场」和「编辑精选历史」接口
	


router
	
feat: 新增「新节目广场」和「编辑精选历史」接口
	


service
	
Merge branch 'dev'
	


utils
	
feat: 新增创建和删除评论接口
	


.gitignore
	
fix: 修复文档问题
	


CHANGELOG.md
	
up 1.9.1
	


Dockerfile
	
fix: module
	


LICENSE
	
first commit
	


README.md
	
chore: README.md
	


build-all.sh
	
up 1.5.0
	


build-darwin.sh
	
fix: 修复文档问题
	


build-linux.sh
	
fix: 修复文档问题
	


build-windows.sh
	
fix: 修复文档问题
	


docker-compose.yml
	
Add Dockerfile
	


go.mod
	
first commit
	


go.sum
	
first commit
	


logo.png
	
first commit
	


main.go
	
feat: 检查端口是否可用
	
Repository files navigation
README
MIT license

⚠️ 本项目登录功能已失效


xyz

小宇宙FM API
免责声明

⚠️ 本项目仅供学习、研究使用，请遵守国家法律，严禁用于任何非法用途

环境

Go 1.22.0 

安装
$ git clone git@github.com:ultrazg/xyz.git
$ cd xyz
$ go mod tidy
运行
$ go run .

服务端启动默认端口为 23020，若想使用其他端口，可执行以下命令：

$ go run . -p 3000

服务启动时打开文档：

$ go run . -d

接口地址：http://localhost:{{port}}/login

文档地址：http://localhost:{{port}}/docs

可在 Releases 下载编译好的可执行文件

作为模块
go get github.com/ultrazg/xyz
package main

import (
	"fmt"

	"github.com/ultrazg/xyz/service"
)

func main() {
	err := service.Start()
	if err != nil {
		fmt.Println("fail")
	}
}
构建

项目内提供对应平台的 build.sh 文件，按需执行即可

功能
 发送验证码
 短信登录
 刷新 token
 搜索节目、单集和用户
 「你可能想搜的内容」
 获取我的信息
 获取节目、单集等内容
 获取「我的订阅」
 订阅/取消订阅节目
 查询节目列表
 查询节目内「最受欢迎」的单集列表
 查询节目公告、荣誉墙、主体等信息
 获取播客音频链接
 查询单集详情
 查询节目详情
 相关节目推荐
 查询「我的贴纸」
 展示「我的贴纸墙」
 查询/更新单集播放进度
 查询单集评论
 查询评论回复
 创建/删除评论
 获取榜单、精选节目、推荐等
 正在收听的人数
 精彩时间点
 创建精彩时间点
 订阅列表更新
 获取分类、分类标签以及查询分类内容
 星标订阅管理
 收藏单集、评论
 查询「我的收藏」
 收听历史
 未读消息
 查询用户信息和用户统计数据
 刷新「大家都在听」推荐
 查询/更新收听数据
 查询「个人主页」收听历史记录
 查询「用户的喜欢」
 查询「新节目广场」
 查询「编辑精选历史」
 查询用户创建的播客节目
 查询首页榜单（最热榜、锋芒榜和新星榜）
 查询关注与被关注列表
 点赞/取消点赞评论
 获取黑名单列表
 拉黑/取消拉黑用户
 获取用户偏好设置
 更新用户偏好设置
 关注/取关用户
 ...
License

The MIT License

About

小宇宙FM API

Topics
api golang podcast fm xyz xiaoyuzhou xiaoyuzhoufm xiaoyuzhouapp
Resources
 Readme
License
 MIT license
 Activity
Stars
 183 stars
Watchers
 4 watching
Forks
 30 forks
Report repository


Releases 19
v1.9.1
Latest
+ 18 releases


Packages
No packages published



Contributors
2
ultrazg unknown
rrbe shawn


Languages
Go
99.3%
 
Other
0.7%
Footer
© 2026 GitHub, Inc.
Footer navigation
Terms
Privacy
Security
Status
Community
Docs
Contact
Manage cookies
Do not share my personal information