# -*- coding: utf-8 -*-
"""
快速启动脚本 - 价值投资主策略（P2.5 生产开关）
=================================================
默认: 价值投资模式（value_investing.run_value_pipeline）,
      实验性权重默认拒绝运行（fail-closed）→ 需显式 --experimental
选项:
  --experimental   允许实验性权重运行（强制标注, 禁止实盘）
  --legacy         调用旧系统对照基线 multi_factor_value.run_full_pipeline
  --top-n N        持仓数（价值模式默认 12; 旧系统默认 30）
"""
import sys
import os
import argparse

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_logger import get_run_logger, log_path


def main():
    parser = argparse.ArgumentParser(description='A股量化选股入口（价值投资模式 / 旧系统对照）')
    parser.add_argument('--experimental', action='store_true',
                        help='允许实验性权重运行（PE_PCTL/PB_PCTL/DY/FCF_YIELD 未经 v3 统计检验, 禁止实盘）')
    parser.add_argument('--legacy', action='store_true',
                        help='调用旧系统对照基线 multi_factor_value.run_full_pipeline')
    parser.add_argument('--top-n', type=int, default=12, help='持仓数（价值模式默认 12）')
    parser.add_argument('--save', type=str, default='selected_stocks.csv', help='选股结果输出文件')
    args = parser.parse_args()

    log = get_run_logger()
    mode = 'LEGACY(对照基线)' if args.legacy else 'VALUE(价值投资)'
    log.info(f"[启动] run.py 入口开始 mode={mode} top_n={args.top_n} experimental={args.experimental}")

    print("\n" + "=" * 78)
    print(f"  A股量化选股入口 | 模式: {mode} | top_n={args.top_n}")
    print("=" * 78)

    try:
        if args.legacy:
            from multi_factor_value import run_full_pipeline
            top_n = args.top_n if args.top_n != 12 else 30  # 旧系统默认 30
            scored, selected = run_full_pipeline(top_n=top_n)
        else:
            from value_investing import run_value_pipeline
            # P2.5 生产开关: 默认 experimental=False → fail-closed 拒绝运行
            scored, selected = run_value_pipeline(top_n=args.top_n,
                                                  experimental=args.experimental)
            if args.experimental:
                print("\n⚠️  实验性权重运行模式: 结果仅供研究/检验, 禁止实盘信号输出 ⚠️")
                log.info("[实验性] 实验性权重运行已显式允许（--experimental）, 禁止实盘")

        # 保存结果
        output_dir = os.path.dirname(os.path.abspath(__file__))
        out2 = os.path.join(output_dir, args.save)
        selected.to_csv(out2, index=False, encoding='utf-8-sig')
        print(f"\n结果已保存到: {out2}")
        log.info(f"[输出] 附加副本: {out2}")
    except RuntimeError as e:
        # fail-closed 拒绝（实验性权重未经检验）
        print(f"\n[拒绝运行] {str(e)[:120]}")
        print("  提示: 如需实验性运行请加 --experimental（仅供研究/检验, 禁止实盘）")
        log.info(f"[拒绝] 生产开关 fail-closed: {str(e)[:150]}")
        sys.exit(1)
    except Exception:
        log.exception("[异常] run.py 入口失败，异常堆栈如下")
        sys.exit(1)


if __name__ == '__main__':
    main()
