# G0共同控制器：实现与验证

2026-09-11；根据本轮EXECUTION_PROTOCOL执行。原C7及冻结环境未修改，0训练、0策略优化、0官方网络/Windows执行。后续G1/训练放行由root统一协调。

## 实现结果

- `engine.py`复用散列固定的C7服务实现，只重新表达其自然调度边界。teacher在独立控制器副本上计算，选中后才提交route_successor与派生状态差；候选按稳定ID排序，teacher位置不固定为0。
- 每个候选包含任务/频道/站、目标、route_successor、服务阶段、状态版本、失败清除/服务进度、控制器patch、服务代码SHA与停止合同。观察快照不含env对象、真实源数、真实位置/类型或场景/seed；网络只读取G16/C12/F16特征和mask，teacher_index不入网络。
- `interface.py`只保存四个接口callable，记录每次接受请求的真实费用与位置/频道/clear成功。clear不换测向频道；同址付费请求保留；底层同request_id重试仍归原适配器处理，不增加自制网络重试层。
- 学习请求端点box±4000、学习时间300000秒、请求10000、连续32次无有效进展调度决策，以及53000秒备用储备均在共同guard执行。每个primitive前后检查，接受后的效果即使触发接管也留在独立账本；不再enter。
- `fallback.py`实现49站/304光学格。返回扫描站通过下一次measure实际付费。正观测频道未clear却全站silent视为矛盾；排空出口同时要求公共10–16源计数一致，不能把0源脚本或17次成功当合法完成。固定16次不同clear成功可给计数证书。
- `geometry.py`保留独立构造常数与纸面上界。实际source真值由外部runner核验，core只报告观测证书、clear频道、正常exit和异常。

## G0实际验证

29个命名合成夹具全部通过；此前27个版本也实际运行过，合计56次测试方法执行、29个独特夹具。合成脚本不是符合比赛分布的新world；0源/矛盾响应明确预期失败，不能拿作全清效果。

使用root登记的20个g0_core新world（Q3/Q4各10），每个分别运行原C7、恒选teacher包装与接受1次请求后强制接管，共60次完整任务执行。所有执行均由冻结LocalEnv真值层复核全清且user_exit；20/20 teacher请求、观测、虚拟费用逐事件相等（排除墙钟字段），teacher均无guard接管。

|版本|实际执行|源分母/清除数|业务primitive|执行本体实际墙钟合计|
|---|---:|---:|---:|---:|
|原C7|20|248/248|3956|0.347153秒|
|teacher包装|20|248/248|3956|2.221353秒|
|强制接管|20|248/248|59941|0.200981秒|

总67853次业务primitive。三路重复相同20world，不是60独立world；分母248在各路重复，不合并成744个独立源。整套连同JSON写盘4.784412秒，属于顺序本地实测，不是受控速度排名。最大的备用尾段34214.027029秒，小于53000纸面储备；teacher和强制接管的macro费用分割误差均为0。执行前后core Python文件散列完全相同。

完整证据在`g0_results_v1/manifest.json`、`rows.json`、`summary.json`和60份逐执行原始JSON；`budget_record.json`统计全部实际执行。完整原始JSON共约148.1MB，含重复事件和完整可回放观察快照；root负责提交时压缩/索引，当前原始文件保留。G1须测生成、序列化、存储与端到端成本，不能仅由小网络参数量估计资源。

## 第二批G0：非teacher候选接续审核

按root追加分配，复用初始registry的另20个g0_audit新world（Q3/Q4各10），分别运行teacher、候选费用贪心（candidate_features第8项最小，排除fallback）及均匀随机合法非fallback。随机选择器使用固定独立种子基数99113000加运行序号，不读取/复用world seed；这是可复现的G0动作覆盖检查，不是训练或选优。

|选择器|实际执行|源分母/清除数|业务primitive|备用/控制器恢复|
|---|---:|---:|---:|---:|
|teacher|20|269/269|3799|0/0|
|费用贪心|20|269/269|3733|0/0|
|随机合法|20|269/269|3768|0/0|

第二批60次全部正常全清，总11300 primitive，费用分割误差0；1751个完整snapshot、24068个候选通过结构与登记的特权键检查。源真N只在runner终局读取env.stats，在线selector看不到配方/seed/真实源数据。该检查结合代码数据流审查，不冒称能阻止恶意Python反射的安全沙箱。

完整60份证据直接gzip保存至`g0_audit_v1`，原始JSON95,218,450字节，压缩10,677,551字节；manifest记录每份压缩与解压后SHA256。全部60份实际解压、解析并逐字节散列核对通过。代码散列执行前后不变。该runner计时段9.611629秒。

两批G0合计40个独特注册world、120次整局执行、79153业务primitive，额度内全部完成。每批三路共享相同world；不把重复执行的清除数当独立源样本。独特合成夹具仍29，不因本批完整world检查重复扩大夹具数。没有额外新world、课程、训练或密封最终集。

## API与成本合同

将执行目录加入Python导入路径：

```python
from core import run_episode, teacher_selector
from core.interface import GuardConfig
result = run_episode(interface_only, mode=3, selector=teacher_selector,
                     guard=GuardConfig())
```

selector接收独立JSON快照，返回Python整数index或`{"index": index, "metadata": {...}}`。metadata应是有限JSON标量/容器，可带old_logprob、old_value、policy_version；core不重算策略概率。候选不重生来解释历史index。

`prefix_time_s + sum(decision.delta_time_s) + tail_time_s == total_time_s`。首版在enter后第一次调度就回调selector，因此正常prefix为0；若未来增加固定前缀，字段已有明确位置。学习macro的实际前缀在中断时封口，fallback尾段只计入tail；选择fallback本身可以是一次真实采样决策，其delta为0、后续费用在tail。不得重复计尾費。无学习选择时不发明PPO/Q采样动作。

terminal仅为`success`或`failure`。success指观测证书成立并正常exit；`true_completeness_checked=False`说明core未读N。root必须再取env.stats核验真实全清后填写训练终端、N与归一reward，失败一次-100。不能把core证书直接当真值评测。

每decision给`snapshot_build_s`、`selector_s`和`prepare_to_macro_s`；每业务事件给`compute_since_previous_response_s`及`backend_call_s`。这些使用同一单调clock，backend时间含底层适配器自身重试；还未验证官方网络延迟。具体字段顺序见SCHEMA.md/schema.py。

## 重现与边界

本轮使用root提供的Python3.12环境：`/Users/t/Documents/Codex/2026-09-10/new-chat/work/rl_execution_runtime/venv/bin/python`。core本身仅标准库，不依赖torch；本地冻结环境与C7由项目相对路径加载，C7源码散列在运行前强制核对。

```bash
python experiments/20260911_rl_execution/tests/test_core_contract.py -v
python experiments/20260911_rl_execution/tests/test_core_g0.py --out NEW_OUTPUT_DIRECTORY
python experiments/20260911_rl_execution/tests/test_core_g0_audit.py --out ANOTHER_NEW_OUTPUT_DIRECTORY
```

后两个命令各会真实重跑20个对应已登记world的三路任务，须计新执行/primitive成本；当前结果已完成，无需重复运行。只使用`data/initial_registry.json`中g0_core/g0_audit配方，不导入会改写冻结案例的generate_cases脚本。

剩余事项：root协调的G1端到端/资源检查；PPO/Q训练器对真实episode和tail的接入；冻结规则/quick/full按本轮协调执行；正式HTTP适配器的通信与现实期限验证。本批已检查两个非teacher选择器的接续完整性；学习模型的效果、可靠性与训练存储规模仍待后续预算内运行。当前条件teacher等价是20个新world的实测，不能升级为所有输入的形式等价；C7端点越box、预算/无进展触发时包装会明确改变路线。真实时间只条件于请求/计算上界；默认30秒现实储备是工程配置，不是数学保证。本轮未支持小于10源的训练课程，也没有新增最终密封验证或替换原C7。

## 已完成的旧v1暴露回归

新增仅恒选teacher的teacher_adapter.py，并完成冻结verify、原14个规则/指标方法、79项nominal、quick120例及full2400例。全部通过，core/C7/冻结环境原实现未改；适配器对core失败明确抛异常。实际候选执行2520局，基准2520行仅读缓存；2400独特旧案例、quick/full重叠120、新world=0，不计成G0新world或学习选择集。候选共499464接受请求，加原规则/nominal165为499629接受请求；包含预期拒绝/异常共499649调用尝试。所有成本单独保留。

全测Q3/Q4各1200局、各15550/15550源清除，平均235.235582543/452.760906820秒/源；这些是既有teacher包装的暴露回归，不能归因神经学习。详细数据、依赖散列、规则输出和CSV在regression_v1/REPORT.md、final_checks.json、quick/及full/。当前无需重跑；无官方网络验证。
