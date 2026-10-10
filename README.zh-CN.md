# DJI Wind Estimator / DJI 无人机姿态反演风场工具

从 DJI 飞控日志（DJI Fly / Airdata 导出的 CSV）中，利用**悬停姿态反演**的方法，
提取无人机在各高度层"感受到"的风速与风向，输出：

- 分高度层的风速风向图（Airdata 风格，风向用旋转箭头表示）
- 逐秒在航风况数据表（时间 / 经纬度 / 高度 / 风速 / 风向）
- 风速、风向随时间变化曲线

## 原理

无人机没有风速计。但在 GPS 定点悬停时，风是唯一需要机身**持续倾斜**去对抗的外力：

```
水平方向：F_wind = T·sin(θ)
竖直方向：m·g    = T·cos(θ)
两式相除：F_wind = m·g·tan(θ)
```

- **风向** = 机身倾斜所指的方向（纯几何解算，可靠性高）；
- **风速** = 由倾角换算，经验线性关系 `v = k · θ`。

### 关于系数 k

纯物理阻力模型 `v = √(2·m·g·tanθ / (ρ·C_d·A))` 对小型无人机系统性偏低
（C_d·A 无官方值，且旋翼滑流等因素使有效阻力更小）。
本工具默认使用 **k = 0.78 m/s/度**，该值由同一架 DJI Mini 3 的实测倾角与
Airdata 官方分析结果（12 个高度层配对）反推标定（隐含 k 分布 0.68–0.96）。

**建议**：用风洞/风墙/风速计的实测数据重新标定 k。若已知某次悬停时的真实风速 v_true
和对应倾角 θ，则 `k = v_true / θ`。标定后通过 `--k` 参数传入即可。

## 日志获取

DJI Fly 的 txt 飞行记录（v13/v14）是 AES 加密的，需要先解密：

1. 在 [DJI Developer](https://developer.dji.com/user/) 创建应用（App Type 选 Open API 或 Mobile SDK），
   激活后获得 **App Key**（ApiKey）；
2. 下载开源解密工具 [dji-log-parser](https://github.com/lvauvillier/dji-log-parser)（MIT 协议）的
   预编译程序，执行：

```bash
dji-log.exe "DJIFlightRecord_2026-09-23_[15-26-15].txt" \
    --api-key YOUR_API_KEY \
    --csv flight_data.csv --kml track.kml --geojson track.geojson
```

也直接支持 **Airdata 导出的 CSV**（自动识别两种列名格式）。

## 安装

```bash
pip install -r requirements.txt
```

## 用法

### 1. 分高度层风速风向图

```bash
python plot_wind_profile.py flight_data.csv -o wind_by_altitude.png
python plot_wind_profile.py flight_data.csv --k 0.78 --bins 0,10,25,50,75,100,150,200,300
```

### 2. 逐秒在航风况表 + 时间序列图

```bash
python export_wind_timeseries.py flight_data.csv -o wind_timeseries.csv --plot wind_timeseries.png
```

输出 CSV 列：`time_s, datetime_utc, latitude, longitude, height_m, wind_speed_ms, wind_dir_deg`
（风向为气象惯例"来风方向"，0°=北，顺时针）。

## 方法与局限性

- 仅使用**悬停帧**（水平地速 < 0.6 m/s 且 GPSAtti/P-GPS 状态），机动倾斜帧被剔除；
- 层内风向采用**矢量平均**（避免角度回绕问题）；
- 风向为纯几何结果，可信度高；风速依赖系数 k，绝对值误差约 ±20%（未标定时）；
- 近地面（< 2 m）受地面效应影响，精度下降；
- 倾角极小（< 1°，微风）时信噪比较低。

## 许可

MIT。解密工具 dji-log-parser 版权归其作者所有（MIT）。

## 致谢

- [lvauvillier/dji-log-parser](https://github.com/lvauvillier/dji-log-parser) — DJI txt 日志解密解析
- Airdata UAV — 分层风况展示风格的参考来源
