"""
CSV 招聘数据分析模块 - 从客户职位信息 CSV 文件中提取招聘预算数据
CSV Recruitment Data Analyzer - Extract hiring budget data from job position CSV

通过解析内部 CSV 数据（客户职位信息），计算：
  1. 渠道分布（BOSS/猎聘/诚猎通等渠道的职位数和预算占比）
  2. 薪资预算分析（各渠道总预算、平均薪资）
  3. HR潜在预算（2个月月薪，即给招聘供应商的预算）
  4. 猎聘占比分析（职位数占比、预算占比）
  5. 薪资分布（各薪资段的职位数）
  6. 职能分布（一级职能的职位数和占比）

CSV 文件格式要求：
  - 编码: UTF-8
  - 必需列: 客户名称, 渠道, 年薪下限, 年薪上限
  - 可选列: 一级职能, 职位名称, 工作地点 等
"""

import csv
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from .config import CSV_FILE_PATH

logger = logging.getLogger("biz_intel_agent.csv_analyzer")


@dataclass
class ChannelStats:
    """单个渠道的统计数据"""
    channel_name: str
    position_count: int = 0
    valid_salary_count: int = 0  # 有薪资数据的职位数
    total_budget: float = 0.0    # 总薪酬预算（万元）
    hr_budget: float = 0.0      # HR潜在预算（万元）

    @property
    def avg_salary(self) -> float:
        """平均年薪（万元）"""
        return self.total_budget / self.valid_salary_count if self.valid_salary_count > 0 else 0


@dataclass
class CSVAnalysisResult:
    """
    CSV 分析结果 - 包含从 CSV 文件中提取的所有招聘预算数据

    用于喂给 LLM 作为精确的内部数据，与网络采集数据互补：
    - 网络采集：提供企业背景、融资信息、战略方向等定性信息
    - CSV 数据：提供精确的职位数、渠道分布、薪资预算等定量数据
    """
    company_name: str
    found: bool = False          # 是否在 CSV 中找到该公司
    total_positions: int = 0     # 总职位数
    total_budget: float = 0.0    # 总薪酬预算（万元）
    total_hr_budget: float = 0.0 # 总HR潜在预算（万元）

    # 各渠道统计
    channels: dict[str, ChannelStats] = field(default_factory=dict)

    # 薪资分布
    salary_distribution: dict[str, int] = field(default_factory=dict)

    # 职能分布
    function_distribution: dict[str, int] = field(default_factory=dict)

    def to_prompt_text(self) -> str:
        """
        将 CSV 分析结果格式化为 LLM 可读的文本

        作为精确的内部数据喂给 LLM，标注"来自内部招聘数据"
        """
        if not self.found:
            return ""

        lines = []
        lines.append(f"## 📊 内部招聘数据分析（来自客户职位数据库）\n")
        lines.append(f"以下为「{self.company_name}」在内部系统中的实际招聘数据，请优先使用这些精确数据：\n")

        # 总体概览
        lines.append("### 总体概览")
        lines.append(f"- 总职位数: **{self.total_positions}** 个")
        lines.append(f"- 总招聘薪酬预算: **{self.total_budget:.1f}万元**（约{self.total_budget/10000:.2f}亿元）")
        lines.append(f"- HR潜在预算（全渠道）: **{self.total_hr_budget:.1f}万元**")
        lines.append(f"- HR预算计算方式: 招聘预算 / 12 × 2（即2个月月薪，用于招聘供应商的预算）")
        lines.append("")

        # 渠道分布
        if self.channels:
            lines.append("### 渠道分布（精确数据）")
            lines.append("| 渠道 | 职位数 | 占比 | 总预算(万) | 预算占比 | 平均年薪(万) | HR潜在预算(万) |")
            lines.append("|------|--------|------|-----------|----------|-------------|--------------|")
            sorted_channels = sorted(self.channels.values(), key=lambda c: c.position_count, reverse=True)
            for ch in sorted_channels:
                pos_ratio = ch.position_count / self.total_positions * 100 if self.total_positions > 0 else 0
                budget_ratio = ch.total_budget / self.total_budget * 100 if self.total_budget > 0 else 0
                lines.append(
                    f"| {ch.channel_name} | {ch.position_count} | {pos_ratio:.1f}% | "
                    f"{ch.total_budget:.1f} | {budget_ratio:.1f}% | "
                    f"{ch.avg_salary:.1f} | {ch.hr_budget:.1f} |"
                )
            lines.append("")

        # 猎聘占比（猎聘渠道的特别分析）
        liepin_stats = self.channels.get("猎聘")
        if liepin_stats:
            liepin_pos_ratio = liepin_stats.position_count / self.total_positions * 100 if self.total_positions > 0 else 0
            liepin_budget_ratio = liepin_stats.total_budget / self.total_budget * 100 if self.total_budget > 0 else 0
            liepin_hr_ratio = liepin_stats.hr_budget / self.total_hr_budget * 100 if self.total_hr_budget > 0 else 0
            lines.append("### 猎聘渠道占比分析")
            lines.append(f"- 猎聘职位占比: **{liepin_pos_ratio:.1f}%**（{liepin_stats.position_count}个职位）")
            lines.append(f"- 猎聘预算占比: **{liepin_budget_ratio:.1f}%**（{liepin_stats.total_budget:.1f}万元）")
            lines.append(f"- 猎聘HR预算占比: **{liepin_hr_ratio:.1f}%**（{liepin_stats.hr_budget:.1f}万元）")
            lines.append("")

        # 薪资分布
        if self.salary_distribution:
            lines.append("### 薪资分布")
            lines.append("| 薪资区间 | 职位数 | 占比 |")
            lines.append("|----------|--------|------|")
            for range_name, count in self.salary_distribution.items():
                if count > 0:
                    ratio = count / self.total_positions * 100
                    lines.append(f"| {range_name} | {count} | {ratio:.1f}% |")
            lines.append("")

        # 职能分布（前10）
        if self.function_distribution:
            lines.append("### 职能分布（Top 10）")
            lines.append("| 职能方向 | 职位数 | 占比 |")
            lines.append("|----------|--------|------|")
            sorted_funcs = sorted(self.function_distribution.items(), key=lambda x: x[1], reverse=True)[:10]
            for func_name, count in sorted_funcs:
                ratio = count / self.total_positions * 100
                lines.append(f"| {func_name} | {count} | {ratio:.1f}% |")
            lines.append("")

        return "\n".join(lines)


class CSVAnalyzer:
    """
    CSV 招聘数据分析器

    读取客户职位信息 CSV 文件，按公司名称过滤，
    计算各维度的招聘预算数据。
    """

    def __init__(self, csv_path: str = None):
        self.csv_path = csv_path or CSV_FILE_PATH
        self._all_data: Optional[list[dict]] = None  # 缓存已读取的数据

    def _load_csv(self) -> list[dict]:
        """加载并缓存 CSV 数据"""
        if self._all_data is not None:
            return self._all_data

        if not self.csv_path or not os.path.exists(self.csv_path):
            logger.warning(f"CSV 文件不存在: {self.csv_path}")
            self._all_data = []
            return self._all_data

        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self._all_data = list(reader)
            logger.info(f"CSV 数据加载完成，共 {len(self._all_data)} 条记录")
        except Exception as e:
            logger.error(f"读取 CSV 文件失败: {e}")
            self._all_data = []

        return self._all_data

    def analyze(self, company_name: str) -> CSVAnalysisResult:
        """
        分析指定公司的招聘数据

        Args:
            company_name: 公司名称（需与 CSV 中的"客户名称"列精确匹配）

        Returns:
            CSVAnalysisResult: 分析结果
        """
        result = CSVAnalysisResult(company_name=company_name)

        all_data = self._load_csv()
        if not all_data:
            return result

        # 过滤指定公司的数据
        company_data = [row for row in all_data if row.get('客户名称') == company_name]

        if not company_data:
            logger.info(f"CSV 中未找到「{company_name}」的数据")
            # 尝试模糊匹配
            fuzzy_matches = [
                row.get('客户名称', '')
                for row in all_data
                if company_name in row.get('客户名称', '') or row.get('客户名称', '') in company_name
            ]
            if fuzzy_matches:
                unique_matches = list(set(fuzzy_matches))[:5]
                logger.info(f"  模糊匹配到: {unique_matches}")
            return result

        result.found = True
        result.total_positions = len(company_data)

        logger.info(f"CSV 中找到「{company_name}」{result.total_positions} 个职位，开始分析...")

        # 1. 按渠道分组统计
        channel_groups: dict[str, list[dict]] = {}
        for row in company_data:
            channel = row.get('渠道', '未知')
            channel_groups.setdefault(channel, []).append(row)

        for channel_name, rows in channel_groups.items():
            stats = ChannelStats(channel_name=channel_name, position_count=len(rows))

            for row in rows:
                try:
                    min_salary = float(row.get('年薪下限', 0) or 0)
                    max_salary = float(row.get('年薪上限', 0) or 0)
                    if min_salary > 0 and max_salary > 0:
                        avg_salary = (min_salary + max_salary) / 2
                        stats.total_budget += avg_salary
                        stats.valid_salary_count += 1
                except (ValueError, TypeError):
                    pass

            # HR潜在预算 = 招聘预算 / 12 × 2（2个月月薪）
            stats.hr_budget = stats.total_budget / 12 * 2

            result.channels[channel_name] = stats
            result.total_budget += stats.total_budget
            result.total_hr_budget += stats.hr_budget

        # 2. 薪资分布
        salary_ranges = {
            '20万以下': 0,
            '20-40万': 0,
            '40-60万': 0,
            '60-80万': 0,
            '80-100万': 0,
            '100万以上': 0,
        }
        for row in company_data:
            try:
                min_salary = float(row.get('年薪下限', 0) or 0)
                max_salary = float(row.get('年薪上限', 0) or 0)
                if min_salary > 0 and max_salary > 0:
                    avg = (min_salary + max_salary) / 2
                    if avg < 20:
                        salary_ranges['20万以下'] += 1
                    elif avg < 40:
                        salary_ranges['20-40万'] += 1
                    elif avg < 60:
                        salary_ranges['40-60万'] += 1
                    elif avg < 80:
                        salary_ranges['60-80万'] += 1
                    elif avg < 100:
                        salary_ranges['80-100万'] += 1
                    else:
                        salary_ranges['100万以上'] += 1
            except (ValueError, TypeError):
                pass
        result.salary_distribution = salary_ranges

        # 3. 职能分布
        func_counts: dict[str, int] = {}
        for row in company_data:
            func = row.get('一级职能', '').strip()
            if func:
                func_counts[func] = func_counts.get(func, 0) + 1
        result.function_distribution = func_counts

        logger.info(
            f"「{company_name}」CSV 分析完成: "
            f"{result.total_positions}个职位, "
            f"总预算{result.total_budget:.1f}万, "
            f"HR预算{result.total_hr_budget:.1f}万, "
            f"{len(result.channels)}个渠道"
        )

        return result

    def list_companies(self, limit: int = 20) -> list[str]:
        """列出 CSV 中的公司名称"""
        all_data = self._load_csv()
        companies = list(set(row.get('客户名称', '') for row in all_data if row.get('客户名称')))
        return sorted(companies)[:limit]

    @property
    def is_available(self) -> bool:
        """CSV 文件是否可用"""
        return bool(self.csv_path) and os.path.exists(self.csv_path)
