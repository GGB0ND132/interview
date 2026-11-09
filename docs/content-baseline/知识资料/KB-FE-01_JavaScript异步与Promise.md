# JavaScript 异步与 Promise

资料 ID：KB-FE-01  
能力：FE-JS  
适用范围：现代浏览器 JavaScript  
版本：0.1.0  
依据：S-JS-01

## Promise 状态与链式调用

Promise 表示一个异步操作最终完成或失败的结果。`then` 注册成功处理，`catch` 处理拒绝，`finally` 用于无论结果如何都执行收尾逻辑。`then` 会返回新的 Promise；若回调返回另一个 Promise，后续链会等待其结果。漏写 `return` 可能使后续步骤过早执行，也使错误处理变得不连贯。

## async 与 await

`async` 函数返回 Promise；`await` 等待一个可等待结果并在当前函数内以更接近顺序代码的写法处理后续逻辑。`await` 不会阻塞整个浏览器线程直到网络完成，但其后续语句会等该操作完成。串行 `await` 与并行启动后统一等待的执行顺序不同，不能笼统说异步操作一定同时发生。

## 错误与取消

被拒绝的 Promise 应被 `catch` 或 `try/catch` 处理，并明确是否要继续向上抛出。Promise 本身没有通用的取消操作；对 `fetch` 等支持取消的底层操作，可使用 `AbortController`。取消请求后仍需处理拒绝或中断结果，不应把“停止等待”误认为服务端动作必然撤销。

## 面试判断边界

“Promise 让 JavaScript 自动开启新线程”不正确。回答应说明异步任务、回调调度和错误传播，而不是把 Promise 当成线程或速度优化开关。

来源：S-JS-01；官方页面链接见 `来源清单.md`。
