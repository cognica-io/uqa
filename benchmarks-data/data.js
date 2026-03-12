window.BENCHMARK_DATA = {
  "lastUpdate": 1773302641782,
  "repoUrl": "https://github.com/cognica-io/uqa",
  "entries": {
    "Benchmark": [
      {
        "commit": {
          "author": {
            "email": "jaepil@cognica.io",
            "name": "Jaepil Jeong",
            "username": "jaepil"
          },
          "committer": {
            "email": "jaepil@cognica.io",
            "name": "Jaepil Jeong",
            "username": "jaepil"
          },
          "distinct": true,
          "id": "a30b372cee83b37e3daf40d402d2f3efda34cfc6",
          "message": "Optimize DPccp join enumerator and add benchmark infrastructure\n\nOptimize the DPccp join enumerator with integer bitmask DP table,\nbytearray connectivity lookup, incremental connected subgraph\nenumeration, and canonical submask enumeration -- yielding a 51x\nspeedup on star-16 topology (92s to 1.8s). Optimize edges_between\nwith adjacency list traversal instead of O(E) linear scan.\n\nAdd 185 pytest-benchmark tests across 8 files covering posting list\noperations, storage backends, SQL compilation, physical execution,\nDPccp join enumeration, BM25/vector/fusion scoring, graph traversal,\nand end-to-end SQL queries. Add GitHub Actions benchmark workflow\nfor regression detection with 150% alert threshold on PRs.\n\nFix DuckDB FDW compatibility with DuckDB 1.4.3 (to_arrow_table\nrenamed to fetch_arrow_table). Add -c flag to usql CLI for single\ncommand execution. Bump version to 0.10.1.",
          "timestamp": "2026-03-11T20:21:22+09:00",
          "tree_id": "0e6dd492626b51452cc76e926a4eba6943001389",
          "url": "https://github.com/cognica-io/uqa/commit/a30b372cee83b37e3daf40d402d2f3efda34cfc6"
        },
        "date": 1773228809396,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 20043.78638046268,
            "unit": "iter/sec",
            "range": "stddev: 0.0000025514045684809177",
            "extra": "mean: 49.89077318119555 usec\nrounds: 3505"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 6567.801729772864,
            "unit": "iter/sec",
            "range": "stddev: 0.0000043661947332260766",
            "extra": "mean: 152.25794583092315 usec\nrounds: 3526"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 10223.764923475324,
            "unit": "iter/sec",
            "range": "stddev: 0.0000029041435810167538",
            "extra": "mean: 97.8113256207454 usec\nrounds: 5316"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 4326.988931563581,
            "unit": "iter/sec",
            "range": "stddev: 0.000007570350498639763",
            "extra": "mean: 231.10759371382179 usec\nrounds: 2609"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 9791.677937247521,
            "unit": "iter/sec",
            "range": "stddev: 0.0000031589129526604887",
            "extra": "mean: 102.1275420217818 usec\nrounds: 5985"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 5583.327439930904,
            "unit": "iter/sec",
            "range": "stddev: 0.00007456603636811288",
            "extra": "mean: 179.10466666314227 usec\nrounds: 9"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 1833.556274417082,
            "unit": "iter/sec",
            "range": "stddev: 0.000024386791866484704",
            "extra": "mean: 545.3882239408858 usec\nrounds: 1487"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4875.092125888918,
            "unit": "iter/sec",
            "range": "stddev: 0.000020105046241133886",
            "extra": "mean: 205.12432876694842 usec\nrounds: 73"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 6915.392762845761,
            "unit": "iter/sec",
            "range": "stddev: 0.000013083958482722786",
            "extra": "mean: 144.60494642801586 usec\nrounds: 224"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 4534.207072385038,
            "unit": "iter/sec",
            "range": "stddev: 0.000007204128465238166",
            "extra": "mean: 220.54572807015407 usec\nrounds: 684"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 11009.266734406885,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034712012793686863",
            "extra": "mean: 90.83257079009034 usec\nrounds: 5594"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 8441.719918002154,
            "unit": "iter/sec",
            "range": "stddev: 0.000003870291650720289",
            "extra": "mean: 118.45927248397307 usec\nrounds: 4859"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 7243.633622336886,
            "unit": "iter/sec",
            "range": "stddev: 0.000008632796170377781",
            "extra": "mean: 138.052261080177 usec\nrounds: 4129"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 6452.496129028083,
            "unit": "iter/sec",
            "range": "stddev: 0.000004999367486053808",
            "extra": "mean: 154.9787834046522 usec\nrounds: 4206"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 4079.9078426327196,
            "unit": "iter/sec",
            "range": "stddev: 0.000015053027994608755",
            "extra": "mean: 245.10357551476235 usec\nrounds: 874"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1637.013188537242,
            "unit": "iter/sec",
            "range": "stddev: 0.000028104156910584996",
            "extra": "mean: 610.8686276947793 usec\nrounds: 1206"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 10654.526447493537,
            "unit": "iter/sec",
            "range": "stddev: 0.0000031444267188032562",
            "extra": "mean: 93.85682272488502 usec\nrounds: 5703"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 9327.18832106842,
            "unit": "iter/sec",
            "range": "stddev: 0.000004102130329527917",
            "extra": "mean: 107.21344585068387 usec\nrounds: 6242"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 4098.129494276741,
            "unit": "iter/sec",
            "range": "stddev: 0.000014460347711397129",
            "extra": "mean: 244.01376320503147 usec\nrounds: 2234"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 5933.04561463577,
            "unit": "iter/sec",
            "range": "stddev: 0.0000072074288841752435",
            "extra": "mean: 168.54749903374713 usec\nrounds: 4140"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 4007.724192938694,
            "unit": "iter/sec",
            "range": "stddev: 0.00026598832431306814",
            "extra": "mean: 249.51816838142807 usec\nrounds: 2916"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1891.0323328299928,
            "unit": "iter/sec",
            "range": "stddev: 0.00001444301053146764",
            "extra": "mean: 528.8116880071885 usec\nrounds: 1109"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1583.2846659147822,
            "unit": "iter/sec",
            "range": "stddev: 0.000034466140842977734",
            "extra": "mean: 631.5983610074471 usec\nrounds: 1072"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1588.7345253399424,
            "unit": "iter/sec",
            "range": "stddev: 0.00034874139846780716",
            "extra": "mean: 629.4317798538617 usec\nrounds: 8081"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 1307.1165265926088,
            "unit": "iter/sec",
            "range": "stddev: 0.00002056434468102545",
            "extra": "mean: 765.0427331117907 usec\nrounds: 903"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 1067.940255165425,
            "unit": "iter/sec",
            "range": "stddev: 0.000021340187295123003",
            "extra": "mean: 936.3819700242492 usec\nrounds: 834"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 95.1201656583057,
            "unit": "iter/sec",
            "range": "stddev: 0.003433668787171764",
            "extra": "mean: 10.51301785566941 msec\nrounds: 97"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 101.24418932068232,
            "unit": "iter/sec",
            "range": "stddev: 0.002315580205688799",
            "extra": "mean: 9.877110051546616 msec\nrounds: 97"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 161.18494628721587,
            "unit": "iter/sec",
            "range": "stddev: 0.003260586816686583",
            "extra": "mean: 6.204053312882565 msec\nrounds: 163"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 183.88558839658077,
            "unit": "iter/sec",
            "range": "stddev: 0.002355944276118646",
            "extra": "mean: 5.438164071038176 msec\nrounds: 183"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 86.19901799645092,
            "unit": "iter/sec",
            "range": "stddev: 0.0023657879675620165",
            "extra": "mean: 11.601060235293785 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 60.18630558414236,
            "unit": "iter/sec",
            "range": "stddev: 0.003409062370076525",
            "extra": "mean: 16.61507531147544 msec\nrounds: 61"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 147.01136638463095,
            "unit": "iter/sec",
            "range": "stddev: 0.0023440962508395205",
            "extra": "mean: 6.802195126760915 msec\nrounds: 142"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 84.41909631496023,
            "unit": "iter/sec",
            "range": "stddev: 0.00007323935827818317",
            "extra": "mean: 11.845661037037022 msec\nrounds: 81"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10723765896141965,
            "unit": "iter/sec",
            "range": "stddev: 0.07190087897168296",
            "extra": "mean: 9.3250823422 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 16.211648572632686,
            "unit": "iter/sec",
            "range": "stddev: 0.000144447231608584",
            "extra": "mean: 61.68404129411777 msec\nrounds: 17"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 19.795175967084717,
            "unit": "iter/sec",
            "range": "stddev: 0.007052731181669611",
            "extra": "mean: 50.51735845454433 msec\nrounds: 22"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 73.0880140545742,
            "unit": "iter/sec",
            "range": "stddev: 0.0037147564951748356",
            "extra": "mean: 13.682133971423939 msec\nrounds: 35"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 176.4858874980863,
            "unit": "iter/sec",
            "range": "stddev: 0.0011625092097902307",
            "extra": "mean: 5.666175432927142 msec\nrounds: 164"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 151.15147517687706,
            "unit": "iter/sec",
            "range": "stddev: 0.0012547524985072932",
            "extra": "mean: 6.615879857142001 msec\nrounds: 140"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 396.80031599398615,
            "unit": "iter/sec",
            "range": "stddev: 0.000017692704102715723",
            "extra": "mean: 2.5201592833790887 msec\nrounds: 367"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 2243.187197569828,
            "unit": "iter/sec",
            "range": "stddev: 0.000011057720639123356",
            "extra": "mean: 445.79427035039987 usec\nrounds: 1683"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 542.7610089149123,
            "unit": "iter/sec",
            "range": "stddev: 0.0009882133937556923",
            "extra": "mean: 1.8424315372233533 msec\nrounds: 497"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 256.24281146258517,
            "unit": "iter/sec",
            "range": "stddev: 0.0025106344148520883",
            "extra": "mean: 3.902548501915782 msec\nrounds: 261"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 232.1533199719508,
            "unit": "iter/sec",
            "range": "stddev: 0.002616804099693363",
            "extra": "mean: 4.3074981659569715 msec\nrounds: 235"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1719.497909850497,
            "unit": "iter/sec",
            "range": "stddev: 0.000009798513503454954",
            "extra": "mean: 581.5651151835048 usec\nrounds: 1146"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 145.18636353923105,
            "unit": "iter/sec",
            "range": "stddev: 0.0024935557269657248",
            "extra": "mean: 6.8876991999995125 msec\nrounds: 45"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 250.84254915117864,
            "unit": "iter/sec",
            "range": "stddev: 0.002626034883016697",
            "extra": "mean: 3.9865644938782556 msec\nrounds: 245"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 75.46202278781405,
            "unit": "iter/sec",
            "range": "stddev: 0.0030764964270789084",
            "extra": "mean: 13.25169884210266 msec\nrounds: 76"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 96.46760960490538,
            "unit": "iter/sec",
            "range": "stddev: 0.0024497989226518004",
            "extra": "mean: 10.366173725000749 msec\nrounds: 40"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 89.55354546225402,
            "unit": "iter/sec",
            "range": "stddev: 0.0033195803594019083",
            "extra": "mean: 11.166503736264586 msec\nrounds: 91"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 95.7627577270482,
            "unit": "iter/sec",
            "range": "stddev: 0.0027003784434662215",
            "extra": "mean: 10.442472875001071 msec\nrounds: 96"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 107.3002368089418,
            "unit": "iter/sec",
            "range": "stddev: 0.0021627851650694516",
            "extra": "mean: 9.319643923811597 msec\nrounds: 105"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 98.49022973835146,
            "unit": "iter/sec",
            "range": "stddev: 0.003051832329120529",
            "extra": "mean: 10.153291373739243 msec\nrounds: 99"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 86.69177133825075,
            "unit": "iter/sec",
            "range": "stddev: 0.004315114503620342",
            "extra": "mean: 11.535120168421026 msec\nrounds: 95"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 185.34084204651742,
            "unit": "iter/sec",
            "range": "stddev: 0.0024266239785619742",
            "extra": "mean: 5.395464857923851 msec\nrounds: 183"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 165.55996328475447,
            "unit": "iter/sec",
            "range": "stddev: 0.003322837129738213",
            "extra": "mean: 6.04010764534933 msec\nrounds: 172"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 176.6547521591737,
            "unit": "iter/sec",
            "range": "stddev: 0.001166871121010678",
            "extra": "mean: 5.66075912353015 msec\nrounds: 170"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 149.46237180012986,
            "unit": "iter/sec",
            "range": "stddev: 0.0017899793474032925",
            "extra": "mean: 6.690647204081978 msec\nrounds: 147"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 41.13031358382989,
            "unit": "iter/sec",
            "range": "stddev: 0.00010027426130797257",
            "extra": "mean: 24.31296804878102 msec\nrounds: 41"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 249.18958667705797,
            "unit": "iter/sec",
            "range": "stddev: 0.0028014359319595518",
            "extra": "mean: 4.013008783131733 msec\nrounds: 249"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 252.1944669524946,
            "unit": "iter/sec",
            "range": "stddev: 0.0026734121102606886",
            "extra": "mean: 3.965194050781329 msec\nrounds: 256"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 56.181012258180296,
            "unit": "iter/sec",
            "range": "stddev: 0.004500780183872737",
            "extra": "mean: 17.799608084747423 msec\nrounds: 59"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 94.5500794213908,
            "unit": "iter/sec",
            "range": "stddev: 0.003170646919682181",
            "extra": "mean: 10.57640571133949 msec\nrounds: 97"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 625683.6442826524,
            "unit": "iter/sec",
            "range": "stddev: 2.2731544260739873e-7",
            "extra": "mean: 1.5982517828902207 usec\nrounds: 61414"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 270287.3064114997,
            "unit": "iter/sec",
            "range": "stddev: 4.0467011205691137e-7",
            "extra": "mean: 3.6997667899266684 usec\nrounds: 67600"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 85329.44835052101,
            "unit": "iter/sec",
            "range": "stddev: 8.33673403884085e-7",
            "extra": "mean: 11.719283545490004 usec\nrounds: 34319"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 780649.8920138719,
            "unit": "iter/sec",
            "range": "stddev: 2.077878083624351e-7",
            "extra": "mean: 1.2809839727515522 usec\nrounds: 108004"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2361121.9069594597,
            "unit": "iter/sec",
            "range": "stddev: 3.1089875624266504e-8",
            "extra": "mean: 423.5274752449154 nsec\nrounds: 118554"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1442501.0506201251,
            "unit": "iter/sec",
            "range": "stddev: 1.7413249856920653e-7",
            "extra": "mean: 693.2403963034233 nsec\nrounds: 195810"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2672811.7156902533,
            "unit": "iter/sec",
            "range": "stddev: 2.736837767787415e-8",
            "extra": "mean: 374.1378392386125 nsec\nrounds: 130107"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 179237.82813883288,
            "unit": "iter/sec",
            "range": "stddev: 4.64251169259129e-7",
            "extra": "mean: 5.579179408631455 usec\nrounds: 86133"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1730.2736364532705,
            "unit": "iter/sec",
            "range": "stddev: 0.00002910898628829909",
            "extra": "mean: 577.943268008064 usec\nrounds: 1541"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1739.1756463150912,
            "unit": "iter/sec",
            "range": "stddev: 0.00004466457738418113",
            "extra": "mean: 574.9850523256622 usec\nrounds: 1548"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 445566.3546451232,
            "unit": "iter/sec",
            "range": "stddev: 7.574130738706804e-7",
            "extra": "mean: 2.24433463068921 usec\nrounds: 71685"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 205821.66427485825,
            "unit": "iter/sec",
            "range": "stddev: 4.6503040898041827e-7",
            "extra": "mean: 4.858575036418812 usec\nrounds: 63276"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 125746.86136482832,
            "unit": "iter/sec",
            "range": "stddev: 6.898100013284402e-7",
            "extra": "mean: 7.952484770961467 usec\nrounds: 48460"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 344467.51425208064,
            "unit": "iter/sec",
            "range": "stddev: 5.724361029828666e-7",
            "extra": "mean: 2.9030313705233812 usec\nrounds: 66623"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 111834.73778764968,
            "unit": "iter/sec",
            "range": "stddev: 6.205371423569238e-7",
            "extra": "mean: 8.94176549954261 usec\nrounds: 46695"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 17326.45177072821,
            "unit": "iter/sec",
            "range": "stddev: 0.0000026321056228179624",
            "extra": "mean: 57.7152213986148 usec\nrounds: 7150"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 11220.255006278205,
            "unit": "iter/sec",
            "range": "stddev: 0.0000028169707250685287",
            "extra": "mean: 89.1245341073316 usec\nrounds: 6978"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 13693.461618086412,
            "unit": "iter/sec",
            "range": "stddev: 0.000002591326732647065",
            "extra": "mean: 73.02755343317965 usec\nrounds: 8272"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 102857.65230950712,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012676511355945975",
            "extra": "mean: 9.72217406820562 usec\nrounds: 32786"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 30075.637580861614,
            "unit": "iter/sec",
            "range": "stddev: 0.000002351948056312636",
            "extra": "mean: 33.2495029344396 usec\nrounds: 15676"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 7037.649681754005,
            "unit": "iter/sec",
            "range": "stddev: 0.000004046453550797493",
            "extra": "mean: 142.09289254516693 usec\nrounds: 4467"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2506.5317611343444,
            "unit": "iter/sec",
            "range": "stddev: 0.00000539314462640629",
            "extra": "mean: 398.9576415929574 usec\nrounds: 1808"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 102462.44616853386,
            "unit": "iter/sec",
            "range": "stddev: 7.429277306214435e-7",
            "extra": "mean: 9.759673298792464 usec\nrounds: 37193"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 20691.725907688116,
            "unit": "iter/sec",
            "range": "stddev: 0.0000018046940654528463",
            "extra": "mean: 48.328496349762915 usec\nrounds: 12191"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1533.230597714373,
            "unit": "iter/sec",
            "range": "stddev: 0.000014319966246145198",
            "extra": "mean: 652.2176125957349 usec\nrounds: 524"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 211.536928621326,
            "unit": "iter/sec",
            "range": "stddev: 0.000020852746922307234",
            "extra": "mean: 4.727306983784889 msec\nrounds: 185"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.4733921679813772,
            "unit": "iter/sec",
            "range": "stddev: 0.00820506774445678",
            "extra": "mean: 2.1124134864000097 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 80945.1215721537,
            "unit": "iter/sec",
            "range": "stddev: 8.245739603662787e-7",
            "extra": "mean: 12.354049022072436 usec\nrounds: 27865"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 7526.268333583244,
            "unit": "iter/sec",
            "range": "stddev: 0.0000028644411501412428",
            "extra": "mean: 132.8679706432818 usec\nrounds: 5348"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 184.14601215847756,
            "unit": "iter/sec",
            "range": "stddev: 0.000032465573143964426",
            "extra": "mean: 5.4304732873573816 msec\nrounds: 174"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 81457.88684738154,
            "unit": "iter/sec",
            "range": "stddev: 8.387536140635537e-7",
            "extra": "mean: 12.27628212199498 usec\nrounds: 33007"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 16941.17797724214,
            "unit": "iter/sec",
            "range": "stddev: 0.000002068432640573536",
            "extra": "mean: 59.027772528176364 usec\nrounds: 9821"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 3115.6598633043477,
            "unit": "iter/sec",
            "range": "stddev: 0.000006782639790853565",
            "extra": "mean: 320.95929718702956 usec\nrounds: 2204"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 922.0873478236066,
            "unit": "iter/sec",
            "range": "stddev: 0.00001152133179405123",
            "extra": "mean: 1.0844959562239844 msec\nrounds: 731"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 7017.6682577370975,
            "unit": "iter/sec",
            "range": "stddev: 0.000003868846856642213",
            "extra": "mean: 142.49747398610404 usec\nrounds: 4709"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1518.1971824802604,
            "unit": "iter/sec",
            "range": "stddev: 0.000007241333971851499",
            "extra": "mean: 658.675968800253 usec\nrounds: 1250"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 181.90667390268385,
            "unit": "iter/sec",
            "range": "stddev: 0.00003777651959151205",
            "extra": "mean: 5.497324416667518 msec\nrounds: 156"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 3093.067271010608,
            "unit": "iter/sec",
            "range": "stddev: 0.000005532906359051956",
            "extra": "mean: 323.3036699112162 usec\nrounds: 2260"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 65.66751037428642,
            "unit": "iter/sec",
            "range": "stddev: 0.0000714406228523423",
            "extra": "mean: 15.228230738462292 msec\nrounds: 65"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1369.8237877238128,
            "unit": "iter/sec",
            "range": "stddev: 0.000018747932804361692",
            "extra": "mean: 730.0209041205688 usec\nrounds: 1262"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 437.34843769613457,
            "unit": "iter/sec",
            "range": "stddev: 0.0002432761915754422",
            "extra": "mean: 2.2865063958334986 msec\nrounds: 432"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1619.2853020490945,
            "unit": "iter/sec",
            "range": "stddev: 0.000008506041053812091",
            "extra": "mean: 617.5563989462318 usec\nrounds: 1519"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 534.8870637671853,
            "unit": "iter/sec",
            "range": "stddev: 0.000013212174317477406",
            "extra": "mean: 1.8695535333328972 msec\nrounds: 525"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 400.71352981270553,
            "unit": "iter/sec",
            "range": "stddev: 0.000020599536123620705",
            "extra": "mean: 2.4955483795803013 msec\nrounds: 382"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1743.2865807946248,
            "unit": "iter/sec",
            "range": "stddev: 0.000013622707107194855",
            "extra": "mean: 573.6291502594944 usec\nrounds: 1158"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1367.0378742371126,
            "unit": "iter/sec",
            "range": "stddev: 0.000013762984708183927",
            "extra": "mean: 731.5086281410152 usec\nrounds: 995"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 934.7378471944239,
            "unit": "iter/sec",
            "range": "stddev: 0.0012282881995856368",
            "extra": "mean: 1.069818669481992 msec\nrounds: 947"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 71.76005142808961,
            "unit": "iter/sec",
            "range": "stddev: 0.009460298720497909",
            "extra": "mean: 13.935330035292615 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 5.787760603407532,
            "unit": "iter/sec",
            "range": "stddev: 0.0438702116584776",
            "extra": "mean: 172.7783971250041 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 301.75854080823615,
            "unit": "iter/sec",
            "range": "stddev: 0.0000299683369189282",
            "extra": "mean: 3.3139078593155307 msec\nrounds: 263"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 72.01586258524357,
            "unit": "iter/sec",
            "range": "stddev: 0.0093284080469152",
            "extra": "mean: 13.885829650604023 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 33.41291906519808,
            "unit": "iter/sec",
            "range": "stddev: 0.01472418265028416",
            "extra": "mean: 29.928543448979017 msec\nrounds: 49"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 24.86620341059977,
            "unit": "iter/sec",
            "range": "stddev: 0.015912716344271938",
            "extra": "mean: 40.215226405400024 msec\nrounds: 37"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 973.0407921238578,
            "unit": "iter/sec",
            "range": "stddev: 0.001198872640342279",
            "extra": "mean: 1.0277061435598176 msec\nrounds: 1017"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 74.08878871729326,
            "unit": "iter/sec",
            "range": "stddev: 0.009286988319872663",
            "extra": "mean: 13.49731878888968 msec\nrounds: 90"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 5.977304385947036,
            "unit": "iter/sec",
            "range": "stddev: 0.04252091357672828",
            "extra": "mean: 167.29949412498613 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 328.23792726484,
            "unit": "iter/sec",
            "range": "stddev: 0.00002782738526314516",
            "extra": "mean: 3.046570542084694 msec\nrounds: 297"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 73.31444929867011,
            "unit": "iter/sec",
            "range": "stddev: 0.009473788664735135",
            "extra": "mean: 13.639876034888793 msec\nrounds: 86"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 33.270888453404396,
            "unit": "iter/sec",
            "range": "stddev: 0.01496683050798742",
            "extra": "mean: 30.05630587233917 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 25.06010611633293,
            "unit": "iter/sec",
            "range": "stddev: 0.016124891551519475",
            "extra": "mean: 39.90406087499565 msec\nrounds: 16"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 17233.421314925487,
            "unit": "iter/sec",
            "range": "stddev: 0.000001841035790346004",
            "extra": "mean: 58.02678305867925 usec\nrounds: 10436"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 1049.660226663187,
            "unit": "iter/sec",
            "range": "stddev: 0.000011412807027091462",
            "extra": "mean: 952.6892365722438 usec\nrounds: 782"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 74.90825861724618,
            "unit": "iter/sec",
            "range": "stddev: 0.00048049354878691144",
            "extra": "mean: 13.3496628871008 msec\nrounds: 62"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1172.3990802250198,
            "unit": "iter/sec",
            "range": "stddev: 0.000007826086977956637",
            "extra": "mean: 852.9518803512443 usec\nrounds: 911"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 1047.3369636012508,
            "unit": "iter/sec",
            "range": "stddev: 0.000007210143035386503",
            "extra": "mean: 954.8025466049786 usec\nrounds: 869"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 1025.9837793590866,
            "unit": "iter/sec",
            "range": "stddev: 0.00000869147312973348",
            "extra": "mean: 974.6742785979343 usec\nrounds: 883"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 1077.216815592587,
            "unit": "iter/sec",
            "range": "stddev: 0.000011148639987145014",
            "extra": "mean: 928.3182229659965 usec\nrounds: 897"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 209.4832693834441,
            "unit": "iter/sec",
            "range": "stddev: 0.00017666989342242953",
            "extra": "mean: 4.773650912281552 msec\nrounds: 171"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 201.64000306313827,
            "unit": "iter/sec",
            "range": "stddev: 0.00019251192026649238",
            "extra": "mean: 4.959333390244376 msec\nrounds: 164"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 127.3981064939495,
            "unit": "iter/sec",
            "range": "stddev: 0.0002562506764971968",
            "extra": "mean: 7.849410226889777 msec\nrounds: 119"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 66.52799537625185,
            "unit": "iter/sec",
            "range": "stddev: 0.010488061406823308",
            "extra": "mean: 15.031266075949807 msec\nrounds: 79"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 19.478572109785564,
            "unit": "iter/sec",
            "range": "stddev: 0.01831883590395525",
            "extra": "mean: 51.33846538461739 msec\nrounds: 13"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 6.81346741637578,
            "unit": "iter/sec",
            "range": "stddev: 0.02171936763779618",
            "extra": "mean: 146.76814885715268 msec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.4333403161765204,
            "unit": "iter/sec",
            "range": "stddev: 0.005510619873070874",
            "extra": "mean: 410.9577247999937 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 45.529603903919735,
            "unit": "iter/sec",
            "range": "stddev: 0.012814332355331927",
            "extra": "mean: 21.963731599999882 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 14.694996153504466,
            "unit": "iter/sec",
            "range": "stddev: 0.01863747887781517",
            "extra": "mean: 68.05037507692847 msec\nrounds: 13"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 6.650395132229146,
            "unit": "iter/sec",
            "range": "stddev: 0.0012652999282141474",
            "extra": "mean: 150.367005285716 msec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 3.2215363073159096,
            "unit": "iter/sec",
            "range": "stddev: 0.035188240766914194",
            "extra": "mean: 310.4109048000055 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 45.36648521533623,
            "unit": "iter/sec",
            "range": "stddev: 0.012849999998522814",
            "extra": "mean: 22.042703887096547 msec\nrounds: 62"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 493830.9145924487,
            "unit": "iter/sec",
            "range": "stddev: 2.5535327361236023e-7",
            "extra": "mean: 2.0249846059663663 usec\nrounds: 71521"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1524668.2710323387,
            "unit": "iter/sec",
            "range": "stddev: 1.348953881585203e-7",
            "extra": "mean: 655.8803767346121 nsec\nrounds: 109686"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 129.82957502060364,
            "unit": "iter/sec",
            "range": "stddev: 0.00028765901806665674",
            "extra": "mean: 7.702405248120873 msec\nrounds: 133"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3713373.5833956017,
            "unit": "iter/sec",
            "range": "stddev: 2.254786389634768e-8",
            "extra": "mean: 269.29690146758 nsec\nrounds: 184878"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4498518.609917752,
            "unit": "iter/sec",
            "range": "stddev: 1.7665873670256698e-8",
            "extra": "mean: 222.29540137842918 nsec\nrounds: 193125"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4289444.876676807,
            "unit": "iter/sec",
            "range": "stddev: 2.0089567541878992e-8",
            "extra": "mean: 233.1304000285317 nsec\nrounds: 195504"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 4131929.8484429014,
            "unit": "iter/sec",
            "range": "stddev: 2.0583007061750755e-8",
            "extra": "mean: 242.01766164467807 nsec\nrounds: 199124"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3628708.980785429,
            "unit": "iter/sec",
            "range": "stddev: 2.1259910272704985e-8",
            "extra": "mean: 275.58010446556983 nsec\nrounds: 190586"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 32603.952251828447,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013992185038865822",
            "extra": "mean: 30.671128220165997 usec\nrounds: 5085"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 32.51313219941291,
            "unit": "iter/sec",
            "range": "stddev: 0.0001048318038892354",
            "extra": "mean: 30.756802939399883 msec\nrounds: 33"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 7672956.332112216,
            "unit": "iter/sec",
            "range": "stddev: 7.782149340128622e-9",
            "extra": "mean: 130.32786278411146 nsec\nrounds: 70517"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 37932.13850128092,
            "unit": "iter/sec",
            "range": "stddev: 0.0000015211492239889445",
            "extra": "mean: 26.362869047476224 usec\nrounds: 12600"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 37830.03443424764,
            "unit": "iter/sec",
            "range": "stddev: 0.0000015080274603158962",
            "extra": "mean: 26.434022991390595 usec\nrounds: 18920"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 37480.118108542105,
            "unit": "iter/sec",
            "range": "stddev: 0.000001432337760340761",
            "extra": "mean: 26.680812400430767 usec\nrounds: 13790"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 205279.16018745516,
            "unit": "iter/sec",
            "range": "stddev: 4.830249601129372e-7",
            "extra": "mean: 4.871415096821461 usec\nrounds: 85303"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 206877.70215773044,
            "unit": "iter/sec",
            "range": "stddev: 4.896041174677788e-7",
            "extra": "mean: 4.833773720270572 usec\nrounds: 111645"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 204367.35218490197,
            "unit": "iter/sec",
            "range": "stddev: 5.022328346334015e-7",
            "extra": "mean: 4.893149464965652 usec\nrounds: 111297"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 200587.94351862915,
            "unit": "iter/sec",
            "range": "stddev: 5.512524837412944e-7",
            "extra": "mean: 4.9853444950799215 usec\nrounds: 23652"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 213.50522163379864,
            "unit": "iter/sec",
            "range": "stddev: 0.00003968686094437064",
            "extra": "mean: 4.68372619811232 msec\nrounds: 212"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 37818.04302836406,
            "unit": "iter/sec",
            "range": "stddev: 0.000001783701103177286",
            "extra": "mean: 26.442404733898737 usec\nrounds: 10224"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 37871.81748131866,
            "unit": "iter/sec",
            "range": "stddev: 0.0000016332793660985032",
            "extra": "mean: 26.404858982362757 usec\nrounds: 13899"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 36336.907907574285,
            "unit": "iter/sec",
            "range": "stddev: 0.000005210459976590039",
            "extra": "mean: 27.520228263328754 usec\nrounds: 13353"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 37217.33345995603,
            "unit": "iter/sec",
            "range": "stddev: 0.0000018394966899644638",
            "extra": "mean: 26.869200639426502 usec\nrounds: 10013"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.8093554113447614,
            "unit": "iter/sec",
            "range": "stddev: 0.0002861613937457309",
            "extra": "mean: 262.51160419998314 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 30190.93793123195,
            "unit": "iter/sec",
            "range": "stddev: 0.0000017025398911802393",
            "extra": "mean: 33.122521806966425 usec\nrounds: 10249"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 30058.730845611466,
            "unit": "iter/sec",
            "range": "stddev: 0.0000020109442063299004",
            "extra": "mean: 33.268204340902784 usec\nrounds: 12763"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 29963.72592279265,
            "unit": "iter/sec",
            "range": "stddev: 0.0000020584618223027877",
            "extra": "mean: 33.37368665621538 usec\nrounds: 13774"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 169132.26142716387,
            "unit": "iter/sec",
            "range": "stddev: 7.893086704681673e-7",
            "extra": "mean: 5.912532544423206 usec\nrounds: 31173"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 18815.384417418878,
            "unit": "iter/sec",
            "range": "stddev: 0.000002285516993065872",
            "extra": "mean: 53.14799728854976 usec\nrounds: 12906"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1893.6972450507033,
            "unit": "iter/sec",
            "range": "stddev: 0.000010265048626140568",
            "extra": "mean: 528.0675158679999 usec\nrounds: 1859"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 185493.80969569576,
            "unit": "iter/sec",
            "range": "stddev: 5.539169922367302e-7",
            "extra": "mean: 5.391015482621812 usec\nrounds: 25900"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 2844.888876647641,
            "unit": "iter/sec",
            "range": "stddev: 0.000005654352357655982",
            "extra": "mean: 351.50757845360187 usec\nrounds: 2237"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 387.244418170993,
            "unit": "iter/sec",
            "range": "stddev: 0.0010662412630923304",
            "extra": "mean: 2.5823483905155644 msec\nrounds: 991"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 350.39901441617474,
            "unit": "iter/sec",
            "range": "stddev: 0.0030354963305473767",
            "extra": "mean: 2.8538893057852137 msec\nrounds: 363"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 56514.720936834834,
            "unit": "iter/sec",
            "range": "stddev: 0.000001014483451223975",
            "extra": "mean: 17.694504784296402 usec\nrounds: 15989"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 29.785252958292944,
            "unit": "iter/sec",
            "range": "stddev: 0.0000785051270190199",
            "extra": "mean: 33.57366148275654 msec\nrounds: 29"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 26870.487498767685,
            "unit": "iter/sec",
            "range": "stddev: 0.0000018448071760610752",
            "extra": "mean: 37.21555107795724 usec\nrounds: 9505"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 9396.061451781301,
            "unit": "iter/sec",
            "range": "stddev: 0.000004686794767100712",
            "extra": "mean: 106.42757128950241 usec\nrounds: 5120"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 12838.674547050981,
            "unit": "iter/sec",
            "range": "stddev: 0.0000025802029365852997",
            "extra": "mean: 77.88966036448818 usec\nrounds: 8780"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3764.8715505166347,
            "unit": "iter/sec",
            "range": "stddev: 0.00012154461611756703",
            "extra": "mean: 265.61331152526964 usec\nrounds: 1987"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 2208656.941402786,
            "unit": "iter/sec",
            "range": "stddev: 5.649954027782708e-8",
            "extra": "mean: 452.76384089095757 nsec\nrounds: 111297"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 2146580.6042881226,
            "unit": "iter/sec",
            "range": "stddev: 3.3193806850746846e-8",
            "extra": "mean: 465.85718607647306 nsec\nrounds: 53548"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jaepil@cognica.io",
            "name": "Jaepil Jeong",
            "username": "jaepil"
          },
          "committer": {
            "email": "jaepil@cognica.io",
            "name": "Jaepil Jeong",
            "username": "jaepil"
          },
          "distinct": true,
          "id": "368ced387a1b1b55927929be8c8dd6ad938587ff",
          "message": "Update GitHub Actions to Node.js 24 compatible versions\n\nUpgrade actions/checkout v4 -> v6 and actions/setup-python v5 -> v6\nto resolve Node.js 20 deprecation warnings in CI workflows.",
          "timestamp": "2026-03-11T20:39:01+09:00",
          "tree_id": "deb5c27560bfc305e0b7010ec58965c025f19270",
          "url": "https://github.com/cognica-io/uqa/commit/368ced387a1b1b55927929be8c8dd6ad938587ff"
        },
        "date": 1773229455256,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 18042.762274179284,
            "unit": "iter/sec",
            "range": "stddev: 0.000004707345158195694",
            "extra": "mean: 55.42388603274369 usec\nrounds: 3229"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 5872.400338059675,
            "unit": "iter/sec",
            "range": "stddev: 0.000008250644335959129",
            "extra": "mean: 170.28811770868032 usec\nrounds: 3823"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 9043.611690804515,
            "unit": "iter/sec",
            "range": "stddev: 0.000014008381281520056",
            "extra": "mean: 110.57529161903241 usec\nrounds: 5250"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 3841.9266928414045,
            "unit": "iter/sec",
            "range": "stddev: 0.000014907643190295037",
            "extra": "mean: 260.2860699719447 usec\nrounds: 2844"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 8717.230240215264,
            "unit": "iter/sec",
            "range": "stddev: 0.000007022400810408558",
            "extra": "mean: 114.71533645935982 usec\nrounds: 6078"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 4667.372995760908,
            "unit": "iter/sec",
            "range": "stddev: 0.00007736569872343502",
            "extra": "mean: 214.25328571516337 usec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 1626.251936101874,
            "unit": "iter/sec",
            "range": "stddev: 0.000027787086198492348",
            "extra": "mean: 614.9108743857979 usec\nrounds: 1425"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4105.097716557851,
            "unit": "iter/sec",
            "range": "stddev: 0.0000161725481816498",
            "extra": "mean: 243.5995606064418 usec\nrounds: 66"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 5725.494162014967,
            "unit": "iter/sec",
            "range": "stddev: 0.000015011090601926609",
            "extra": "mean: 174.6574132647567 usec\nrounds: 196"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 3771.6539559786816,
            "unit": "iter/sec",
            "range": "stddev: 0.000012280121232755562",
            "extra": "mean: 265.13567036414844 usec\nrounds: 631"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 9437.644818104536,
            "unit": "iter/sec",
            "range": "stddev: 0.00000704243467216181",
            "extra": "mean: 105.9586389690856 usec\nrounds: 5199"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 7159.934351603724,
            "unit": "iter/sec",
            "range": "stddev: 0.000007988289208738894",
            "extra": "mean: 139.66608503554423 usec\nrounds: 4504"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 6137.556111813675,
            "unit": "iter/sec",
            "range": "stddev: 0.000009160547046802287",
            "extra": "mean: 162.93130063205166 usec\nrounds: 3639"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 5452.4174166977755,
            "unit": "iter/sec",
            "range": "stddev: 0.000010234735508549308",
            "extra": "mean: 183.40488696583398 usec\nrounds: 3813"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 3326.38613235849,
            "unit": "iter/sec",
            "range": "stddev: 0.000016679744602617636",
            "extra": "mean: 300.6265539265507 usec\nrounds: 955"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1339.9849832604043,
            "unit": "iter/sec",
            "range": "stddev: 0.0000639680232192349",
            "extra": "mean: 746.2770198863237 usec\nrounds: 1056"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 9012.002301692226,
            "unit": "iter/sec",
            "range": "stddev: 0.000007562243979185689",
            "extra": "mean: 110.96313189048179 usec\nrounds: 5914"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 7897.448807702929,
            "unit": "iter/sec",
            "range": "stddev: 0.000053477323007640684",
            "extra": "mean: 126.62316962721313 usec\nrounds: 6249"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 3447.143989733494,
            "unit": "iter/sec",
            "range": "stddev: 0.00001631523340117817",
            "extra": "mean: 290.09522171927375 usec\nrounds: 1989"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 5117.521939030964,
            "unit": "iter/sec",
            "range": "stddev: 0.000013945074225774837",
            "extra": "mean: 195.40707629860333 usec\nrounds: 3696"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 3461.8101659055187,
            "unit": "iter/sec",
            "range": "stddev: 0.000013397720808406832",
            "extra": "mean: 288.8662150942717 usec\nrounds: 2650"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1775.1303375707855,
            "unit": "iter/sec",
            "range": "stddev: 0.00003033972294323973",
            "extra": "mean: 563.3389159291091 usec\nrounds: 1130"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1474.5116966775647,
            "unit": "iter/sec",
            "range": "stddev: 0.00001670076994475582",
            "extra": "mean: 678.1906188016306 usec\nrounds: 968"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1633.1916946680462,
            "unit": "iter/sec",
            "range": "stddev: 0.0003389492732110344",
            "extra": "mean: 612.2979949412825 usec\nrounds: 6721"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 1207.3825168497303,
            "unit": "iter/sec",
            "range": "stddev: 0.00006300414488895897",
            "extra": "mean: 828.2379329205237 usec\nrounds: 969"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 950.8309951486096,
            "unit": "iter/sec",
            "range": "stddev: 0.0005703967017143014",
            "extra": "mean: 1.0517116134226414 msec\nrounds: 745"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 97.16820671663555,
            "unit": "iter/sec",
            "range": "stddev: 0.002592005808224826",
            "extra": "mean: 10.291432082473499 msec\nrounds: 97"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 99.79815158520853,
            "unit": "iter/sec",
            "range": "stddev: 0.0025430304938142377",
            "extra": "mean: 10.020225666666695 msec\nrounds: 99"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 160.42637952906315,
            "unit": "iter/sec",
            "range": "stddev: 0.002329980056460864",
            "extra": "mean: 6.233388816325173 msec\nrounds: 49"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 169.49044347550182,
            "unit": "iter/sec",
            "range": "stddev: 0.002499716274771425",
            "extra": "mean: 5.900037662858201 msec\nrounds: 175"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 84.84939702235616,
            "unit": "iter/sec",
            "range": "stddev: 0.0028806795836128505",
            "extra": "mean: 11.78558758333332 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 61.31350637115303,
            "unit": "iter/sec",
            "range": "stddev: 0.0025958836052583927",
            "extra": "mean: 16.309620166666626 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 143.05047394374543,
            "unit": "iter/sec",
            "range": "stddev: 0.001759710491254906",
            "extra": "mean: 6.990539579709814 msec\nrounds: 138"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 81.07420227180911,
            "unit": "iter/sec",
            "range": "stddev: 0.002519294948474471",
            "extra": "mean: 12.334379765432699 msec\nrounds: 81"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10788555648937473,
            "unit": "iter/sec",
            "range": "stddev: 0.05207749374675876",
            "extra": "mean: 9.2690813538 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 13.671080128156882,
            "unit": "iter/sec",
            "range": "stddev: 0.00033268547782852327",
            "extra": "mean: 73.14710985713597 msec\nrounds: 14"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 18.152314054921543,
            "unit": "iter/sec",
            "range": "stddev: 0.009051270117671194",
            "extra": "mean: 55.08939504761791 msec\nrounds: 21"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 69.03647158510155,
            "unit": "iter/sec",
            "range": "stddev: 0.004041010766982932",
            "extra": "mean: 14.485097181817814 msec\nrounds: 33"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 167.06203585476496,
            "unit": "iter/sec",
            "range": "stddev: 0.0015029301058726546",
            "extra": "mean: 5.98580039374923 msec\nrounds: 160"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 140.23317189364496,
            "unit": "iter/sec",
            "range": "stddev: 0.0020509287203302794",
            "extra": "mean: 7.130980398549465 msec\nrounds: 138"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 337.5143088917958,
            "unit": "iter/sec",
            "range": "stddev: 0.00003170069133418762",
            "extra": "mean: 2.962837348388069 msec\nrounds: 310"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 1909.641727922448,
            "unit": "iter/sec",
            "range": "stddev: 0.000016340517194812997",
            "extra": "mean: 523.6584357045485 usec\nrounds: 1462"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 466.98521195875185,
            "unit": "iter/sec",
            "range": "stddev: 0.0013736516979706388",
            "extra": "mean: 2.141395432642369 msec\nrounds: 386"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 225.1562717596249,
            "unit": "iter/sec",
            "range": "stddev: 0.002886891175468677",
            "extra": "mean: 4.441359737327646 msec\nrounds: 217"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 209.55572838436606,
            "unit": "iter/sec",
            "range": "stddev: 0.0026736477720601735",
            "extra": "mean: 4.772000306122889 msec\nrounds: 196"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1572.7401410341959,
            "unit": "iter/sec",
            "range": "stddev: 0.00003887152311230379",
            "extra": "mean: 635.8329478018055 usec\nrounds: 1092"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 122.74835617846902,
            "unit": "iter/sec",
            "range": "stddev: 0.003862780753865211",
            "extra": "mean: 8.14674860937492 msec\nrounds: 128"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 222.53956757409378,
            "unit": "iter/sec",
            "range": "stddev: 0.002881037387300617",
            "extra": "mean: 4.4935829205610975 msec\nrounds: 214"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 73.3847405738073,
            "unit": "iter/sec",
            "range": "stddev: 0.0030395399481818494",
            "extra": "mean: 13.626811135132947 msec\nrounds: 74"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 92.37113556898811,
            "unit": "iter/sec",
            "range": "stddev: 0.00281055788942304",
            "extra": "mean: 10.825892675674018 msec\nrounds: 37"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 88.37530546789901,
            "unit": "iter/sec",
            "range": "stddev: 0.002830819002981837",
            "extra": "mean: 11.315378144443697 msec\nrounds: 90"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 88.96727803360864,
            "unit": "iter/sec",
            "range": "stddev: 0.003511556253149642",
            "extra": "mean: 11.24008761538412 msec\nrounds: 91"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 105.35014726007168,
            "unit": "iter/sec",
            "range": "stddev: 0.0022974181929960153",
            "extra": "mean: 9.492155692306333 msec\nrounds: 39"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 99.71748877097535,
            "unit": "iter/sec",
            "range": "stddev: 0.0022941367327365216",
            "extra": "mean: 10.028331161615343 msec\nrounds: 99"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 85.07452923197226,
            "unit": "iter/sec",
            "range": "stddev: 0.00437698735310855",
            "extra": "mean: 11.754399454545382 msec\nrounds: 88"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 164.48782963915787,
            "unit": "iter/sec",
            "range": "stddev: 0.003009136633548631",
            "extra": "mean: 6.079477139395246 msec\nrounds: 165"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 151.14375398219758,
            "unit": "iter/sec",
            "range": "stddev: 0.003752418415996317",
            "extra": "mean: 6.6162178300651755 msec\nrounds: 153"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 168.74135295549942,
            "unit": "iter/sec",
            "range": "stddev: 0.0012549890781440938",
            "extra": "mean: 5.926229596272828 msec\nrounds: 161"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 145.2884025479081,
            "unit": "iter/sec",
            "range": "stddev: 0.001231724193864558",
            "extra": "mean: 6.8828618283572585 msec\nrounds: 134"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 39.5350339218788,
            "unit": "iter/sec",
            "range": "stddev: 0.0023664710169957904",
            "extra": "mean: 25.294021550000423 msec\nrounds: 40"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 223.0531014504923,
            "unit": "iter/sec",
            "range": "stddev: 0.0029875389016640053",
            "extra": "mean: 4.483237370370995 msec\nrounds: 216"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 227.38126378265557,
            "unit": "iter/sec",
            "range": "stddev: 0.0025845358086233243",
            "extra": "mean: 4.3978997361711345 msec\nrounds: 235"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 54.06281457829926,
            "unit": "iter/sec",
            "range": "stddev: 0.004608646209854496",
            "extra": "mean: 18.4970021964302 msec\nrounds: 56"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 93.71971153375213,
            "unit": "iter/sec",
            "range": "stddev: 0.0030240368019850764",
            "extra": "mean: 10.670113934781597 msec\nrounds: 92"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 632092.9816416753,
            "unit": "iter/sec",
            "range": "stddev: 3.5199804815536833e-7",
            "extra": "mean: 1.5820457259354381 usec\nrounds: 62306"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 262955.5933305378,
            "unit": "iter/sec",
            "range": "stddev: 5.650354494917748e-7",
            "extra": "mean: 3.8029234797184555 usec\nrounds: 59592"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 77586.75688983887,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011481819391880607",
            "extra": "mean: 12.888797522750494 usec\nrounds: 30759"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 779809.4419835736,
            "unit": "iter/sec",
            "range": "stddev: 3.1620148640332996e-7",
            "extra": "mean: 1.2823645703190456 usec\nrounds: 120701"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2175653.7035336266,
            "unit": "iter/sec",
            "range": "stddev: 5.7331698486106573e-8",
            "extra": "mean: 459.6319710144276 nsec\nrounds: 105286"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1456005.7049652894,
            "unit": "iter/sec",
            "range": "stddev: 3.3107818897977245e-7",
            "extra": "mean: 686.8104957211273 nsec\nrounds: 190840"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2422227.5534847537,
            "unit": "iter/sec",
            "range": "stddev: 1.7828112703126623e-7",
            "extra": "mean: 412.84312803780284 nsec\nrounds: 121581"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 165319.02793704186,
            "unit": "iter/sec",
            "range": "stddev: 7.54420421254711e-7",
            "extra": "mean: 6.048910476178387 usec\nrounds: 77376"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1605.9401762107486,
            "unit": "iter/sec",
            "range": "stddev: 0.000013379187215362293",
            "extra": "mean: 622.6882014743053 usec\nrounds: 1221"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1658.695025625968,
            "unit": "iter/sec",
            "range": "stddev: 0.000015846402216138624",
            "extra": "mean: 602.8835829073606 usec\nrounds: 1369"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 448666.2259898255,
            "unit": "iter/sec",
            "range": "stddev: 6.64363492015802e-7",
            "extra": "mean: 2.2288283406976954 usec\nrounds: 71706"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 195915.85671020916,
            "unit": "iter/sec",
            "range": "stddev: 7.525581177007488e-7",
            "extra": "mean: 5.1042320759118525 usec\nrounds: 63699"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 118331.24110209504,
            "unit": "iter/sec",
            "range": "stddev: 9.865984652346682e-7",
            "extra": "mean: 8.450853643436476 usec\nrounds: 50008"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 340372.3340367347,
            "unit": "iter/sec",
            "range": "stddev: 5.920127311212988e-7",
            "extra": "mean: 2.937959111248081 usec\nrounds: 90416"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 103782.18746749844,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010992295528600095",
            "extra": "mean: 9.635564872952507 usec\nrounds: 48857"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 16135.727700228621,
            "unit": "iter/sec",
            "range": "stddev: 0.000003852344360674131",
            "extra": "mean: 61.9742733998809 usec\nrounds: 6624"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 10360.490510732252,
            "unit": "iter/sec",
            "range": "stddev: 0.000005485486203715913",
            "extra": "mean: 96.52052660673907 usec\nrounds: 7780"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 12509.29110560921,
            "unit": "iter/sec",
            "range": "stddev: 0.000010104901884742537",
            "extra": "mean: 79.94058108949088 usec\nrounds: 7985"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 92442.55663544533,
            "unit": "iter/sec",
            "range": "stddev: 0.0000016596282411021651",
            "extra": "mean: 10.817528597176088 usec\nrounds: 29531"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 26962.67157550849,
            "unit": "iter/sec",
            "range": "stddev: 0.000002395384264734789",
            "extra": "mean: 37.08831289954029 usec\nrounds: 14551"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 6258.896981785933,
            "unit": "iter/sec",
            "range": "stddev: 0.000005611340978076079",
            "extra": "mean: 159.7725610295405 usec\nrounds: 4039"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2171.255950105771,
            "unit": "iter/sec",
            "range": "stddev: 0.000011051113828150752",
            "extra": "mean: 460.5629290048858 usec\nrounds: 1648"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 90596.24735337989,
            "unit": "iter/sec",
            "range": "stddev: 0.0000016634935676374794",
            "extra": "mean: 11.037984786493398 usec\nrounds: 35495"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 18526.85493480214,
            "unit": "iter/sec",
            "range": "stddev: 0.0000033145456919394303",
            "extra": "mean: 53.97570194828535 usec\nrounds: 11498"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1361.6137512471448,
            "unit": "iter/sec",
            "range": "stddev: 0.000013129261052274413",
            "extra": "mean: 734.4226650796297 usec\nrounds: 630"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 187.23251230258217,
            "unit": "iter/sec",
            "range": "stddev: 0.00005452111244830072",
            "extra": "mean: 5.3409527421387315 msec\nrounds: 159"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.3838590991878354,
            "unit": "iter/sec",
            "range": "stddev: 0.029869434161032375",
            "extra": "mean: 2.6051225622000063 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 72681.74580361394,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012889146959296764",
            "extra": "mean: 13.758612825591719 usec\nrounds: 26603"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 6410.6269050685105,
            "unit": "iter/sec",
            "range": "stddev: 0.00000842872501181663",
            "extra": "mean: 155.990984159343 usec\nrounds: 4419"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 159.30981987424454,
            "unit": "iter/sec",
            "range": "stddev: 0.00004702913095019962",
            "extra": "mean: 6.27707696103967 msec\nrounds: 154"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 72751.23540818064,
            "unit": "iter/sec",
            "range": "stddev: 0.000001470357612250048",
            "extra": "mean: 13.745471047871073 usec\nrounds: 29566"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 14921.191675046515,
            "unit": "iter/sec",
            "range": "stddev: 0.000005106817867500014",
            "extra": "mean: 67.01877583091114 usec\nrounds: 8904"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 2749.2243710826556,
            "unit": "iter/sec",
            "range": "stddev: 0.000006552220715332195",
            "extra": "mean: 363.7389550734253 usec\nrounds: 1892"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 812.4769816160792,
            "unit": "iter/sec",
            "range": "stddev: 0.000020430830402593347",
            "extra": "mean: 1.2308040998416019 msec\nrounds: 631"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6223.765442093138,
            "unit": "iter/sec",
            "range": "stddev: 0.000006174501676496778",
            "extra": "mean: 160.67443564577624 usec\nrounds: 4281"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1326.8187117621312,
            "unit": "iter/sec",
            "range": "stddev: 0.000011513157869683453",
            "extra": "mean: 753.6824670432276 usec\nrounds: 1062"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 153.18178760018824,
            "unit": "iter/sec",
            "range": "stddev: 0.00044211838892222496",
            "extra": "mean: 6.52819121428487 msec\nrounds: 140"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 2684.2558998579357,
            "unit": "iter/sec",
            "range": "stddev: 0.000011000167562315033",
            "extra": "mean: 372.5427221946034 usec\nrounds: 2005"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 53.64679733296188,
            "unit": "iter/sec",
            "range": "stddev: 0.0003012422064869429",
            "extra": "mean: 18.640441735849457 msec\nrounds: 53"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1248.994386200307,
            "unit": "iter/sec",
            "range": "stddev: 0.00001800050792916624",
            "extra": "mean: 800.6441110133422 usec\nrounds: 1135"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 401.3790585854661,
            "unit": "iter/sec",
            "range": "stddev: 0.000021778092858550256",
            "extra": "mean: 2.491410497409069 msec\nrounds: 386"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1483.4819997239695,
            "unit": "iter/sec",
            "range": "stddev: 0.000012618489924666042",
            "extra": "mean: 674.0897430410813 usec\nrounds: 1401"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 493.1995457537212,
            "unit": "iter/sec",
            "range": "stddev: 0.000021356638261516322",
            "extra": "mean: 2.0275768877113873 msec\nrounds: 472"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 345.27171091646875,
            "unit": "iter/sec",
            "range": "stddev: 0.0003634721763306089",
            "extra": "mean: 2.8962697156557056 msec\nrounds: 313"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1604.388622693077,
            "unit": "iter/sec",
            "range": "stddev: 0.000019036757152941756",
            "extra": "mean: 623.2903835489877 usec\nrounds: 1009"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1241.023666983138,
            "unit": "iter/sec",
            "range": "stddev: 0.00003940975681221841",
            "extra": "mean: 805.7864056943785 usec\nrounds: 843"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 846.8386977899044,
            "unit": "iter/sec",
            "range": "stddev: 0.0014510533229361716",
            "extra": "mean: 1.1808624270593902 msec\nrounds: 850"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 61.33345408686185,
            "unit": "iter/sec",
            "range": "stddev: 0.010696378454167575",
            "extra": "mean: 16.30431572602738 msec\nrounds: 73"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 5.50160512699313,
            "unit": "iter/sec",
            "range": "stddev: 0.047238149088352215",
            "extra": "mean: 181.76513525000004 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 263.6461557053193,
            "unit": "iter/sec",
            "range": "stddev: 0.00018771014354533",
            "extra": "mean: 3.7929625688064754 msec\nrounds: 218"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 61.41152694554802,
            "unit": "iter/sec",
            "range": "stddev: 0.01067722549768169",
            "extra": "mean: 16.283587947368147 msec\nrounds: 76"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 30.02350909387038,
            "unit": "iter/sec",
            "range": "stddev: 0.01594101692603907",
            "extra": "mean: 33.30723257143052 msec\nrounds: 42"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 23.054732643404837,
            "unit": "iter/sec",
            "range": "stddev: 0.01728905857095617",
            "extra": "mean: 43.37504214285762 msec\nrounds: 14"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 913.7034628678191,
            "unit": "iter/sec",
            "range": "stddev: 0.000973281767728208",
            "extra": "mean: 1.0944469848689464 msec\nrounds: 727"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 62.306136204579545,
            "unit": "iter/sec",
            "range": "stddev: 0.011005870043698813",
            "extra": "mean: 16.049783551278843 msec\nrounds: 78"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 5.958296427098796,
            "unit": "iter/sec",
            "range": "stddev: 0.04328196976443906",
            "extra": "mean: 167.83320740000818 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 294.6750998155157,
            "unit": "iter/sec",
            "range": "stddev: 0.00016245128143909656",
            "extra": "mean: 3.3935680368855734 msec\nrounds: 244"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 63.304164272648954,
            "unit": "iter/sec",
            "range": "stddev: 0.010590781986179456",
            "extra": "mean: 15.79674909999653 msec\nrounds: 20"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 29.501449418354575,
            "unit": "iter/sec",
            "range": "stddev: 0.01675513142637645",
            "extra": "mean: 33.89663964706228 msec\nrounds: 17"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 22.877411949994492,
            "unit": "iter/sec",
            "range": "stddev: 0.017163352208373266",
            "extra": "mean: 43.711238062495994 msec\nrounds: 16"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 15483.219808271328,
            "unit": "iter/sec",
            "range": "stddev: 0.00000407534611838114",
            "extra": "mean: 64.58604943823039 usec\nrounds: 10680"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 970.1482076610082,
            "unit": "iter/sec",
            "range": "stddev: 0.00001700981083514228",
            "extra": "mean: 1.0307703422046859 msec\nrounds: 526"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 48.34772975967415,
            "unit": "iter/sec",
            "range": "stddev: 0.0019562035263729826",
            "extra": "mean: 20.68349444680812 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1094.734819387557,
            "unit": "iter/sec",
            "range": "stddev: 0.00001570825378900554",
            "extra": "mean: 913.4632262445476 usec\nrounds: 663"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 981.5701249858348,
            "unit": "iter/sec",
            "range": "stddev: 0.00001742262025252787",
            "extra": "mean: 1.018775912739226 msec\nrounds: 573"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 908.1533261998397,
            "unit": "iter/sec",
            "range": "stddev: 0.000021904438846666467",
            "extra": "mean: 1.1011356465372337 msec\nrounds: 563"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 902.3568426821229,
            "unit": "iter/sec",
            "range": "stddev: 0.00003444972840484207",
            "extra": "mean: 1.1082090285120987 msec\nrounds: 491"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 133.01252514147413,
            "unit": "iter/sec",
            "range": "stddev: 0.00031074991017819364",
            "extra": "mean: 7.51808898399895 msec\nrounds: 125"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 126.3471670383901,
            "unit": "iter/sec",
            "range": "stddev: 0.00030239051578207437",
            "extra": "mean: 7.91470060975846 msec\nrounds: 123"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 86.26091107942564,
            "unit": "iter/sec",
            "range": "stddev: 0.00020229337564311135",
            "extra": "mean: 11.592736356322964 msec\nrounds: 87"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 55.32631805329393,
            "unit": "iter/sec",
            "range": "stddev: 0.012423040264891359",
            "extra": "mean: 18.07458069117729 msec\nrounds: 68"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 15.04507519573724,
            "unit": "iter/sec",
            "range": "stddev: 0.02320016809812899",
            "extra": "mean: 66.46693266666641 msec\nrounds: 21"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 5.3304622859347175,
            "unit": "iter/sec",
            "range": "stddev: 0.026397890068055648",
            "extra": "mean: 187.60098962498262 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 1.8761177492113736,
            "unit": "iter/sec",
            "range": "stddev: 0.004138746341744264",
            "extra": "mean: 533.0155851999962 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 38.34593371316422,
            "unit": "iter/sec",
            "range": "stddev: 0.015546387920256404",
            "extra": "mean: 26.07838441176615 msec\nrounds: 17"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 12.442702443980444,
            "unit": "iter/sec",
            "range": "stddev: 0.023035555167070263",
            "extra": "mean: 80.36839300000959 msec\nrounds: 11"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 5.77444689929585,
            "unit": "iter/sec",
            "range": "stddev: 0.001950898609215789",
            "extra": "mean: 173.17675916665584 msec\nrounds: 6"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 2.7636080209568368,
            "unit": "iter/sec",
            "range": "stddev: 0.04004133093720111",
            "extra": "mean: 361.84581620000245 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 37.9533508139387,
            "unit": "iter/sec",
            "range": "stddev: 0.015616764253059617",
            "extra": "mean: 26.348134711540183 msec\nrounds: 52"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 438510.79736025294,
            "unit": "iter/sec",
            "range": "stddev: 4.516123470991493e-7",
            "extra": "mean: 2.2804455580564937 usec\nrounds: 87405"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1459106.2218071064,
            "unit": "iter/sec",
            "range": "stddev: 2.3677882105239184e-7",
            "extra": "mean: 685.3510629003403 nsec\nrounds: 101751"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 127.68340461075208,
            "unit": "iter/sec",
            "range": "stddev: 0.00021491674113844272",
            "extra": "mean: 7.8318713622067 msec\nrounds: 127"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3296244.768802621,
            "unit": "iter/sec",
            "range": "stddev: 4.0201458838630815e-8",
            "extra": "mean: 303.3755288637911 nsec\nrounds: 194213"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4342611.439819285,
            "unit": "iter/sec",
            "range": "stddev: 2.893503069890409e-8",
            "extra": "mean: 230.2761860825417 nsec\nrounds: 195351"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4082151.1725165783,
            "unit": "iter/sec",
            "range": "stddev: 3.060521628852811e-8",
            "extra": "mean: 244.9688798231146 nsec\nrounds: 191205"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 3919450.537746599,
            "unit": "iter/sec",
            "range": "stddev: 3.2242830004065505e-8",
            "extra": "mean: 255.13780321231656 nsec\nrounds: 196851"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3443103.1549712727,
            "unit": "iter/sec",
            "range": "stddev: 3.804861610059663e-8",
            "extra": "mean: 290.435678221306 nsec\nrounds: 199641"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 29830.063241546937,
            "unit": "iter/sec",
            "range": "stddev: 0.000004143581501789199",
            "extra": "mean: 33.52322762116081 usec\nrounds: 4960"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 30.465559656259288,
            "unit": "iter/sec",
            "range": "stddev: 0.00014249425730348324",
            "extra": "mean: 32.82394977420169 msec\nrounds: 31"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 6486969.81115625,
            "unit": "iter/sec",
            "range": "stddev: 1.2503041991477053e-8",
            "extra": "mean: 154.15518017059466 nsec\nrounds: 65799"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 32730.526413834952,
            "unit": "iter/sec",
            "range": "stddev: 0.000003927261652971439",
            "extra": "mean: 30.552518079187003 usec\nrounds: 10869"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 32461.891946949363,
            "unit": "iter/sec",
            "range": "stddev: 0.000004074472655957959",
            "extra": "mean: 30.805351753195513 usec\nrounds: 18024"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 32367.967361494782,
            "unit": "iter/sec",
            "range": "stddev: 0.0000041400393905377695",
            "extra": "mean: 30.894741978441584 usec\nrounds: 11999"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 215758.40816750354,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011079859352793887",
            "extra": "mean: 4.634813579193875 usec\nrounds: 71757"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 216951.4097107494,
            "unit": "iter/sec",
            "range": "stddev: 8.212670664104635e-7",
            "extra": "mean: 4.609327043936938 usec\nrounds: 113948"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 215981.56998084023,
            "unit": "iter/sec",
            "range": "stddev: 7.456622180034495e-7",
            "extra": "mean: 4.630024682609309 usec\nrounds: 35815"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 189845.3619234335,
            "unit": "iter/sec",
            "range": "stddev: 9.293491770658539e-7",
            "extra": "mean: 5.267444987164394 usec\nrounds: 22522"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 224.69329518881304,
            "unit": "iter/sec",
            "range": "stddev: 0.000030577274334511314",
            "extra": "mean: 4.450511080714204 msec\nrounds: 223"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 32548.490288656063,
            "unit": "iter/sec",
            "range": "stddev: 0.0000041855369293542745",
            "extra": "mean: 30.7233911966886 usec\nrounds: 8906"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 32559.506975941877,
            "unit": "iter/sec",
            "range": "stddev: 0.000003929678785063693",
            "extra": "mean: 30.712995769220246 usec\nrounds: 15126"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 32550.63063325246,
            "unit": "iter/sec",
            "range": "stddev: 0.000004356719774101574",
            "extra": "mean: 30.72137100097959 usec\nrounds: 15035"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 31838.154451904436,
            "unit": "iter/sec",
            "range": "stddev: 0.00000390479177605754",
            "extra": "mean: 31.40885573347622 usec\nrounds: 14903"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.410212732671151,
            "unit": "iter/sec",
            "range": "stddev: 0.0006168376887075996",
            "extra": "mean: 293.2368384000256 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 26366.301643805964,
            "unit": "iter/sec",
            "range": "stddev: 0.00000422513685646025",
            "extra": "mean: 37.927200162898934 usec\nrounds: 9787"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 26348.610927872465,
            "unit": "iter/sec",
            "range": "stddev: 0.000004372268196469464",
            "extra": "mean: 37.95266485726447 usec\nrounds: 13263"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 26265.754126355652,
            "unit": "iter/sec",
            "range": "stddev: 0.000004536382025801127",
            "extra": "mean: 38.0723886772616 usec\nrounds: 13389"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 166909.0522631941,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012128976799236503",
            "extra": "mean: 5.991286790264248 usec\nrounds: 27079"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 18828.727956150775,
            "unit": "iter/sec",
            "range": "stddev: 0.0000044318915703884175",
            "extra": "mean: 53.11033237767558 usec\nrounds: 11505"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1895.0644895144276,
            "unit": "iter/sec",
            "range": "stddev: 0.0000121278137926663",
            "extra": "mean: 527.68652757365 usec\nrounds: 1759"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 199603.3983892674,
            "unit": "iter/sec",
            "range": "stddev: 0.000001115457633999451",
            "extra": "mean: 5.0099347409396096 usec\nrounds: 19277"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 3253.423893015089,
            "unit": "iter/sec",
            "range": "stddev: 0.000008998766836270282",
            "extra": "mean: 307.3684932808606 usec\nrounds: 2307"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 412.7792776448856,
            "unit": "iter/sec",
            "range": "stddev: 0.0009545743098220517",
            "extra": "mean: 2.422602233584751 msec\nrounds: 929"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 371.55293861529117,
            "unit": "iter/sec",
            "range": "stddev: 0.00003086660517188102",
            "extra": "mean: 2.6914065159242564 msec\nrounds: 314"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 47374.93329927636,
            "unit": "iter/sec",
            "range": "stddev: 0.0000036268987131008505",
            "extra": "mean: 21.108209138423735 usec\nrounds: 14794"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 28.768649690040714,
            "unit": "iter/sec",
            "range": "stddev: 0.0008254527658790406",
            "extra": "mean: 34.76006037037552 msec\nrounds: 27"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 21793.43084361785,
            "unit": "iter/sec",
            "range": "stddev: 0.000007961159421305484",
            "extra": "mean: 45.88538661836474 usec\nrounds: 8564"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 8152.196356889015,
            "unit": "iter/sec",
            "range": "stddev: 0.00002207438584644113",
            "extra": "mean: 122.66632895255889 usec\nrounds: 5098"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 11794.15761574173,
            "unit": "iter/sec",
            "range": "stddev: 0.000013515200095704864",
            "extra": "mean: 84.78774259089893 usec\nrounds: 8605"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3345.4602471636604,
            "unit": "iter/sec",
            "range": "stddev: 0.0001067759206063951",
            "extra": "mean: 298.91253403707833 usec\nrounds: 1043"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 1666324.3602204125,
            "unit": "iter/sec",
            "range": "stddev: 2.7484881945985875e-7",
            "extra": "mean: 600.1232556353707 nsec\nrounds: 143823"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1898332.8621887004,
            "unit": "iter/sec",
            "range": "stddev: 1.1015154936582527e-7",
            "extra": "mean: 526.7780060695155 nsec\nrounds: 187970"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jaepil@cognica.io",
            "name": "Jaepil Jeong",
            "username": "jaepil"
          },
          "committer": {
            "email": "jaepil@cognica.io",
            "name": "Jaepil Jeong",
            "username": "jaepil"
          },
          "distinct": true,
          "id": "1898e53c7f5c6649c46b43c8d0df0ac9cae767ca",
          "message": "Add readme field to pyproject.toml for PyPI long description",
          "timestamp": "2026-03-11T21:15:03+09:00",
          "tree_id": "c94040d93d08833b2d6a3fd9c128797b49a352be",
          "url": "https://github.com/cognica-io/uqa/commit/1898e53c7f5c6649c46b43c8d0df0ac9cae767ca"
        },
        "date": 1773231623423,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 17865.270912684726,
            "unit": "iter/sec",
            "range": "stddev: 0.000004043408411905577",
            "extra": "mean: 55.974522014663584 usec\nrounds: 3157"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 5834.164301624522,
            "unit": "iter/sec",
            "range": "stddev: 0.000008155013447221624",
            "extra": "mean: 171.40415461414932 usec\nrounds: 3706"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 9084.451431476007,
            "unit": "iter/sec",
            "range": "stddev: 0.000006071287690721372",
            "extra": "mean: 110.07819322311285 usec\nrounds: 6050"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 3806.873488341161,
            "unit": "iter/sec",
            "range": "stddev: 0.000015000463850433324",
            "extra": "mean: 262.68275083544955 usec\nrounds: 2693"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 8738.51911900387,
            "unit": "iter/sec",
            "range": "stddev: 0.000008128624552133147",
            "extra": "mean: 114.43586566347102 usec\nrounds: 5449"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 4839.597587502371,
            "unit": "iter/sec",
            "range": "stddev: 0.00006271284636853158",
            "extra": "mean: 206.62874999821668 usec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 1629.438404188801,
            "unit": "iter/sec",
            "range": "stddev: 0.00003423345192031222",
            "extra": "mean: 613.7083779474558 usec\nrounds: 1442"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4155.914530071496,
            "unit": "iter/sec",
            "range": "stddev: 0.000013566707165449295",
            "extra": "mean: 240.62092537374596 usec\nrounds: 67"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 5717.213504115422,
            "unit": "iter/sec",
            "range": "stddev: 0.000013670133666134924",
            "extra": "mean: 174.91038235325126 usec\nrounds: 204"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 3795.7500550840605,
            "unit": "iter/sec",
            "range": "stddev: 0.000012224832603792247",
            "extra": "mean: 263.4525417869892 usec\nrounds: 694"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 9480.46411796913,
            "unit": "iter/sec",
            "range": "stddev: 0.000007585286866169158",
            "extra": "mean: 105.48006801741013 usec\nrounds: 5528"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 7274.839827075948,
            "unit": "iter/sec",
            "range": "stddev: 0.000009895162488851907",
            "extra": "mean: 137.46007111773628 usec\nrounds: 5287"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 6077.066300278176,
            "unit": "iter/sec",
            "range": "stddev: 0.000029741228335458866",
            "extra": "mean: 164.55308377238293 usec\nrounds: 3987"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 5525.214516414055,
            "unit": "iter/sec",
            "range": "stddev: 0.000009874479508081171",
            "extra": "mean: 180.98844796509633 usec\nrounds: 3882"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 3321.7855377812625,
            "unit": "iter/sec",
            "range": "stddev: 0.00001791861490763627",
            "extra": "mean: 301.0429146090916 usec\nrounds: 972"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1341.9820133048152,
            "unit": "iter/sec",
            "range": "stddev: 0.00002013853875537036",
            "extra": "mean: 745.1664702549647 usec\nrounds: 1059"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 9075.628300865148,
            "unit": "iter/sec",
            "range": "stddev: 0.00000762524895083119",
            "extra": "mean: 110.18520887470386 usec\nrounds: 5927"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 7969.376007415608,
            "unit": "iter/sec",
            "range": "stddev: 0.000009968919151890836",
            "extra": "mean: 125.48033861992293 usec\nrounds: 5927"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 3431.4806558700775,
            "unit": "iter/sec",
            "range": "stddev: 0.00003331754991211687",
            "extra": "mean: 291.41939013683367 usec\nrounds: 2048"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 5122.481042203521,
            "unit": "iter/sec",
            "range": "stddev: 0.000011815447464975484",
            "extra": "mean: 195.21790159126354 usec\nrounds: 4085"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 3428.263955189837,
            "unit": "iter/sec",
            "range": "stddev: 0.00026404341053078444",
            "extra": "mean: 291.69282560234655 usec\nrounds: 2781"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1770.6523648481425,
            "unit": "iter/sec",
            "range": "stddev: 0.000019306907044568413",
            "extra": "mean: 564.7635977860417 usec\nrounds: 1084"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1460.7079436701881,
            "unit": "iter/sec",
            "range": "stddev: 0.00002917742226957419",
            "extra": "mean: 684.5995493715128 usec\nrounds: 1114"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1626.628771278294,
            "unit": "iter/sec",
            "range": "stddev: 0.00034354822901260174",
            "extra": "mean: 614.7684202180595 usec\nrounds: 6875"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 1211.328169690914,
            "unit": "iter/sec",
            "range": "stddev: 0.000024219702360217756",
            "extra": "mean: 825.5401178816497 usec\nrounds: 1001"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 974.9120495733328,
            "unit": "iter/sec",
            "range": "stddev: 0.00002573290546497331",
            "extra": "mean: 1.0257335525165032 msec\nrounds: 914"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 95.83403422457619,
            "unit": "iter/sec",
            "range": "stddev: 0.0028626622815168465",
            "extra": "mean: 10.434706292929436 msec\nrounds: 99"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 100.21865124059543,
            "unit": "iter/sec",
            "range": "stddev: 0.002374973706820256",
            "extra": "mean: 9.978182579999952 msec\nrounds: 100"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 151.81844249018275,
            "unit": "iter/sec",
            "range": "stddev: 0.0030171685667878326",
            "extra": "mean: 6.5868150377360415 msec\nrounds: 159"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 181.92054915835044,
            "unit": "iter/sec",
            "range": "stddev: 0.00003369463579191677",
            "extra": "mean: 5.496905130434509 msec\nrounds: 46"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 83.71650377109192,
            "unit": "iter/sec",
            "range": "stddev: 0.00300903986966573",
            "extra": "mean: 11.945076000000244 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 59.670047714973194,
            "unit": "iter/sec",
            "range": "stddev: 0.0034613213838077116",
            "extra": "mean: 16.7588268870961 msec\nrounds: 62"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 136.8837337679011,
            "unit": "iter/sec",
            "range": "stddev: 0.002559785921860649",
            "extra": "mean: 7.30546992307787 msec\nrounds: 143"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 80.96938709413399,
            "unit": "iter/sec",
            "range": "stddev: 0.0019096683815197919",
            "extra": "mean: 12.350346666665668 msec\nrounds: 81"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10808415326414968,
            "unit": "iter/sec",
            "range": "stddev: 0.037922126515376645",
            "extra": "mean: 9.252050090599997 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 13.705530469263778,
            "unit": "iter/sec",
            "range": "stddev: 0.0003115471684441344",
            "extra": "mean: 72.96324664285082 msec\nrounds: 14"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 19.017479489566362,
            "unit": "iter/sec",
            "range": "stddev: 0.007079188595020911",
            "extra": "mean: 52.58320381250492 msec\nrounds: 16"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 69.06459108491451,
            "unit": "iter/sec",
            "range": "stddev: 0.00409763842231932",
            "extra": "mean: 14.479199605634468 msec\nrounds: 71"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 165.012767390674,
            "unit": "iter/sec",
            "range": "stddev: 0.0018178099403021997",
            "extra": "mean: 6.060137138555237 msec\nrounds: 166"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 141.7745425331191,
            "unit": "iter/sec",
            "range": "stddev: 0.00187661804590442",
            "extra": "mean: 7.053452489655511 msec\nrounds: 145"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 345.90178623968217,
            "unit": "iter/sec",
            "range": "stddev: 0.000031109802488436735",
            "extra": "mean: 2.890994032933615 msec\nrounds: 334"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 1922.559865390111,
            "unit": "iter/sec",
            "range": "stddev: 0.00001618987695017166",
            "extra": "mean: 520.139849999983 usec\nrounds: 1500"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 468.9077291490266,
            "unit": "iter/sec",
            "range": "stddev: 0.0012306015276249672",
            "extra": "mean: 2.132615731915529 msec\nrounds: 470"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 227.59254077083148,
            "unit": "iter/sec",
            "range": "stddev: 0.0025448117002585943",
            "extra": "mean: 4.393817111110529 msec\nrounds: 234"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 212.2751588245938,
            "unit": "iter/sec",
            "range": "stddev: 0.002328768757432788",
            "extra": "mean: 4.710866808613791 msec\nrounds: 209"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1579.116366116995,
            "unit": "iter/sec",
            "range": "stddev: 0.00001558310731695162",
            "extra": "mean: 633.2655537343162 usec\nrounds: 1098"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 125.14452486105158,
            "unit": "iter/sec",
            "range": "stddev: 0.0034255682404316485",
            "extra": "mean: 7.990761090909119 msec\nrounds: 132"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 228.15680038111984,
            "unit": "iter/sec",
            "range": "stddev: 0.0023482941843497754",
            "extra": "mean: 4.382950665198541 msec\nrounds: 227"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 71.84945520263238,
            "unit": "iter/sec",
            "range": "stddev: 0.0036289332632691434",
            "extra": "mean: 13.917990013699681 msec\nrounds: 73"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 90.60380444557751,
            "unit": "iter/sec",
            "range": "stddev: 0.0030441026974483486",
            "extra": "mean: 11.037064129030748 msec\nrounds: 93"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 87.0581674909291,
            "unit": "iter/sec",
            "range": "stddev: 0.002940889392252763",
            "extra": "mean: 11.486573044444034 msec\nrounds: 90"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 93.23970738871832,
            "unit": "iter/sec",
            "range": "stddev: 0.0022652089644657576",
            "extra": "mean: 10.725044382979226 msec\nrounds: 94"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 102.6857762974294,
            "unit": "iter/sec",
            "range": "stddev: 0.0026925150357823852",
            "extra": "mean: 9.738447096153799 msec\nrounds: 104"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 97.05008973492582,
            "unit": "iter/sec",
            "range": "stddev: 0.003253906214279764",
            "extra": "mean: 10.303957500001422 msec\nrounds: 98"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 84.40727029323507,
            "unit": "iter/sec",
            "range": "stddev: 0.004448329037035034",
            "extra": "mean: 11.847320693181405 msec\nrounds: 88"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 169.80667189655733,
            "unit": "iter/sec",
            "range": "stddev: 0.0022667747737431165",
            "extra": "mean: 5.889050111112119 msec\nrounds: 171"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 156.63027395719914,
            "unit": "iter/sec",
            "range": "stddev: 0.002740813013482067",
            "extra": "mean: 6.384461794871536 msec\nrounds: 156"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 167.66059621950873,
            "unit": "iter/sec",
            "range": "stddev: 0.0010931808552342077",
            "extra": "mean: 5.964430656627008 msec\nrounds: 166"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 143.9206886187296,
            "unit": "iter/sec",
            "range": "stddev: 0.0013432004722624476",
            "extra": "mean: 6.94827136805307 msec\nrounds: 144"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 39.14446135362287,
            "unit": "iter/sec",
            "range": "stddev: 0.0029985128985583814",
            "extra": "mean: 25.546398275000115 msec\nrounds: 40"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 226.7730602439925,
            "unit": "iter/sec",
            "range": "stddev: 0.002437767280899056",
            "extra": "mean: 4.409694868182612 msec\nrounds: 220"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 229.75884615943167,
            "unit": "iter/sec",
            "range": "stddev: 0.002144212477586953",
            "extra": "mean: 4.352389545454503 msec\nrounds: 220"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 55.866534655037896,
            "unit": "iter/sec",
            "range": "stddev: 0.003574584589411365",
            "extra": "mean: 17.899803633333512 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 94.00585575596521,
            "unit": "iter/sec",
            "range": "stddev: 0.0027169749969797267",
            "extra": "mean: 10.637635197917383 msec\nrounds: 96"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 634772.9069524,
            "unit": "iter/sec",
            "range": "stddev: 3.623312987537846e-7",
            "extra": "mean: 1.575366542975325 usec\nrounds: 90827"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 264191.2278798804,
            "unit": "iter/sec",
            "range": "stddev: 5.846445713755015e-7",
            "extra": "mean: 3.7851370313274333 usec\nrounds: 81215"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 77473.25078814151,
            "unit": "iter/sec",
            "range": "stddev: 0.000001187484471220159",
            "extra": "mean: 12.907680906983003 usec\nrounds: 36469"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 772161.8252905929,
            "unit": "iter/sec",
            "range": "stddev: 3.505319795681856e-7",
            "extra": "mean: 1.2950653182364504 usec\nrounds: 167197"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2197932.569044032,
            "unit": "iter/sec",
            "range": "stddev: 4.637582286912409e-8",
            "extra": "mean: 454.9730114945881 nsec\nrounds: 100817"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1727692.7497243455,
            "unit": "iter/sec",
            "range": "stddev: 8.780211687545615e-8",
            "extra": "mean: 578.8066194984905 nsec\nrounds: 190877"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2439600.0907347794,
            "unit": "iter/sec",
            "range": "stddev: 5.8342158986920403e-8",
            "extra": "mean: 409.9032475846529 nsec\nrounds: 171204"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 170096.08172723348,
            "unit": "iter/sec",
            "range": "stddev: 7.528125207672949e-7",
            "extra": "mean: 5.8790301919100205 usec\nrounds: 91912"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1634.0574579354984,
            "unit": "iter/sec",
            "range": "stddev: 0.00001622005945166841",
            "extra": "mean: 611.9735846152072 usec\nrounds: 715"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1645.5093613561921,
            "unit": "iter/sec",
            "range": "stddev: 0.00001566092126804463",
            "extra": "mean: 607.7145615117147 usec\nrounds: 1455"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 442901.0689660702,
            "unit": "iter/sec",
            "range": "stddev: 5.008014805896858e-7",
            "extra": "mean: 2.257840565466344 usec\nrounds: 70587"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 195595.35690529968,
            "unit": "iter/sec",
            "range": "stddev: 7.59886128146171e-7",
            "extra": "mean: 5.112595798908276 usec\nrounds: 68602"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 119120.12667731447,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011505594752828718",
            "extra": "mean: 8.394886975808115 usec\nrounds: 53608"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 337276.3722540438,
            "unit": "iter/sec",
            "range": "stddev: 5.928211166308834e-7",
            "extra": "mean: 2.9649275261024766 usec\nrounds: 100726"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 104292.37422340899,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010197643297910028",
            "extra": "mean: 9.58842875566203 usec\nrounds: 50411"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 15883.147661866165,
            "unit": "iter/sec",
            "range": "stddev: 0.0000037542915208933063",
            "extra": "mean: 62.959812581790636 usec\nrounds: 6883"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 10480.230389891516,
            "unit": "iter/sec",
            "range": "stddev: 0.000007833118861132152",
            "extra": "mean: 95.4177496865459 usec\nrounds: 7978"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 12525.123742331845,
            "unit": "iter/sec",
            "range": "stddev: 0.00000483299694724535",
            "extra": "mean: 79.8395305764721 usec\nrounds: 8029"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 92735.14718777865,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012774256749396907",
            "extra": "mean: 10.783397992296363 usec\nrounds: 29488"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 26695.66472588973,
            "unit": "iter/sec",
            "range": "stddev: 0.000002229493612593622",
            "extra": "mean: 37.45926577472296 usec\nrounds: 13978"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 6136.804101029683,
            "unit": "iter/sec",
            "range": "stddev: 0.000005427473766270272",
            "extra": "mean: 162.95126641442116 usec\nrounds: 3701"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2108.7396602753893,
            "unit": "iter/sec",
            "range": "stddev: 0.000009092934678463923",
            "extra": "mean: 474.21690730158974 usec\nrounds: 1575"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 91920.51682952396,
            "unit": "iter/sec",
            "range": "stddev: 0.000001252331452448435",
            "extra": "mean: 10.878964071259551 usec\nrounds: 36656"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 18358.90771990636,
            "unit": "iter/sec",
            "range": "stddev: 0.0000033010240962529037",
            "extra": "mean: 54.46947145530401 usec\nrounds: 10107"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1338.3040329921898,
            "unit": "iter/sec",
            "range": "stddev: 0.00000947482475072203",
            "extra": "mean: 747.2143663530571 usec\nrounds: 636"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 184.2249904837826,
            "unit": "iter/sec",
            "range": "stddev: 0.00004119534750010597",
            "extra": "mean: 5.428145211862723 msec\nrounds: 118"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.39980666558667527,
            "unit": "iter/sec",
            "range": "stddev: 0.0172743533112266",
            "extra": "mean: 2.5012089244000038 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 72621.58930360952,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013474409452006744",
            "extra": "mean: 13.770009849540664 usec\nrounds: 26905"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 6626.569360692341,
            "unit": "iter/sec",
            "range": "stddev: 0.000008465513718525794",
            "extra": "mean: 150.90764852350694 usec\nrounds: 4979"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 159.88026644173388,
            "unit": "iter/sec",
            "range": "stddev: 0.00005450325788808652",
            "extra": "mean: 6.254680594771437 msec\nrounds: 153"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 72520.97931369301,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013475993529051104",
            "extra": "mean: 13.789113294712301 usec\nrounds: 19692"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 14901.680885732427,
            "unit": "iter/sec",
            "range": "stddev: 0.0000033708185420725214",
            "extra": "mean: 67.10652359744512 usec\nrounds: 8984"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 2740.647197428962,
            "unit": "iter/sec",
            "range": "stddev: 0.000025551292818486523",
            "extra": "mean: 364.87731837141 usec\nrounds: 1916"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 785.6920339268079,
            "unit": "iter/sec",
            "range": "stddev: 0.000018815323522311634",
            "extra": "mean: 1.272763317965823 msec\nrounds: 629"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6169.306910232106,
            "unit": "iter/sec",
            "range": "stddev: 0.000005144148986064117",
            "extra": "mean: 162.0927625340619 usec\nrounds: 3710"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1340.471043618397,
            "unit": "iter/sec",
            "range": "stddev: 0.00001473489729066079",
            "extra": "mean: 746.0064167448575 usec\nrounds: 1063"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 158.57257689718622,
            "unit": "iter/sec",
            "range": "stddev: 0.000026446376519161827",
            "extra": "mean: 6.306260638296687 msec\nrounds: 141"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 2754.073930742559,
            "unit": "iter/sec",
            "range": "stddev: 0.000017867022388086594",
            "extra": "mean: 363.0984589184133 usec\nrounds: 1996"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 52.58332597537118,
            "unit": "iter/sec",
            "range": "stddev: 0.00016696019447877815",
            "extra": "mean: 19.017435307693866 msec\nrounds: 52"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1250.1399857338483,
            "unit": "iter/sec",
            "range": "stddev: 0.000012873235115386174",
            "extra": "mean: 799.9104191623685 usec\nrounds: 1169"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 399.2719711865114,
            "unit": "iter/sec",
            "range": "stddev: 0.000027711021697037412",
            "extra": "mean: 2.5045584768405176 msec\nrounds: 367"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1459.2246340233432,
            "unit": "iter/sec",
            "range": "stddev: 0.000012482470165147077",
            "extra": "mean: 685.295448475826 usec\nrounds: 1378"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 483.681468535739,
            "unit": "iter/sec",
            "range": "stddev: 0.000028535818970078928",
            "extra": "mean: 2.0674763559317766 msec\nrounds: 472"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 350.12235131343846,
            "unit": "iter/sec",
            "range": "stddev: 0.0001411185153619396",
            "extra": "mean: 2.856144419939573 msec\nrounds: 331"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1589.0618984739638,
            "unit": "iter/sec",
            "range": "stddev: 0.000019728641299896662",
            "extra": "mean: 629.3021064568584 usec\nrounds: 1146"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1259.6185348344763,
            "unit": "iter/sec",
            "range": "stddev: 0.000017396493520009335",
            "extra": "mean: 793.8911442990221 usec\nrounds: 991"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 855.8411854607546,
            "unit": "iter/sec",
            "range": "stddev: 0.0012993925289185",
            "extra": "mean: 1.1684410811120705 msec\nrounds: 863"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 71.70636447634654,
            "unit": "iter/sec",
            "range": "stddev: 0.008254534009940239",
            "extra": "mean: 13.945763493976404 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 6.443461110135164,
            "unit": "iter/sec",
            "range": "stddev: 0.0395933206094891",
            "extra": "mean: 155.19609460000652 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 273.5906620034073,
            "unit": "iter/sec",
            "range": "stddev: 0.00003543554476267623",
            "extra": "mean: 3.6550955090256187 msec\nrounds: 277"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 72.54732927306907,
            "unit": "iter/sec",
            "range": "stddev: 0.007747992926537651",
            "extra": "mean: 13.784104942526378 msec\nrounds: 87"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 35.334985319041955,
            "unit": "iter/sec",
            "range": "stddev: 0.012126755004745098",
            "extra": "mean: 28.300563619057225 msec\nrounds: 21"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 25.84217913876885,
            "unit": "iter/sec",
            "range": "stddev: 0.013117007913368593",
            "extra": "mean: 38.69642705555679 msec\nrounds: 36"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 921.2668275438467,
            "unit": "iter/sec",
            "range": "stddev: 0.0010955065240740463",
            "extra": "mean: 1.0854618554605517 msec\nrounds: 934"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 73.80626146075838,
            "unit": "iter/sec",
            "range": "stddev: 0.008087955702926575",
            "extra": "mean: 13.54898595604499 msec\nrounds: 91"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 6.500898014549711,
            "unit": "iter/sec",
            "range": "stddev: 0.03886694867570675",
            "extra": "mean: 153.82490199998404 msec\nrounds: 9"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 295.62179684555935,
            "unit": "iter/sec",
            "range": "stddev: 0.00003588525415094682",
            "extra": "mean: 3.382700499998742 msec\nrounds: 296"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 74.19223305189317,
            "unit": "iter/sec",
            "range": "stddev: 0.007904828935585192",
            "extra": "mean: 13.47849982221937 msec\nrounds: 90"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 36.48289047873397,
            "unit": "iter/sec",
            "range": "stddev: 0.011258211657557237",
            "extra": "mean: 27.41010887234673 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 25.645155862787384,
            "unit": "iter/sec",
            "range": "stddev: 0.013639723448009192",
            "extra": "mean: 38.99371894444433 msec\nrounds: 36"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 15969.400678450036,
            "unit": "iter/sec",
            "range": "stddev: 0.000003917000245701359",
            "extra": "mean: 62.61975763119611 usec\nrounds: 10942"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 991.0052574021106,
            "unit": "iter/sec",
            "range": "stddev: 0.00001242131272643587",
            "extra": "mean: 1.009076382320583 msec\nrounds: 905"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 78.87789326816775,
            "unit": "iter/sec",
            "range": "stddev: 0.0006094067678278653",
            "extra": "mean: 12.6778233870955 msec\nrounds: 62"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1105.8562682716715,
            "unit": "iter/sec",
            "range": "stddev: 0.000013506164840923972",
            "extra": "mean: 904.276648504138 usec\nrounds: 936"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 982.28403852412,
            "unit": "iter/sec",
            "range": "stddev: 0.0000152228710827486",
            "extra": "mean: 1.0180354772968705 msec\nrounds: 947"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 917.6891642072861,
            "unit": "iter/sec",
            "range": "stddev: 0.000014804658899016968",
            "extra": "mean: 1.0896935901643943 msec\nrounds: 854"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 912.1054542134292,
            "unit": "iter/sec",
            "range": "stddev: 0.000013926459515887742",
            "extra": "mean: 1.0963644558647752 msec\nrounds: 827"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 180.21788546984496,
            "unit": "iter/sec",
            "range": "stddev: 0.00016061465627657768",
            "extra": "mean: 5.548838825807472 msec\nrounds: 155"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 167.95119660691884,
            "unit": "iter/sec",
            "range": "stddev: 0.00017671945986389866",
            "extra": "mean: 5.9541106000003605 msec\nrounds: 140"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 113.52431468091464,
            "unit": "iter/sec",
            "range": "stddev: 0.0002701115542526954",
            "extra": "mean: 8.808685635414074 msec\nrounds: 96"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 67.49265466945496,
            "unit": "iter/sec",
            "range": "stddev: 0.008289213876522622",
            "extra": "mean: 14.816427134145139 msec\nrounds: 82"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 18.361487909043976,
            "unit": "iter/sec",
            "range": "stddev: 0.017582565960644128",
            "extra": "mean: 54.46181730770569 msec\nrounds: 13"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 6.8019555368230895,
            "unit": "iter/sec",
            "range": "stddev: 0.02284218278904794",
            "extra": "mean: 147.01654466666193 msec\nrounds: 9"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.5112487407010486,
            "unit": "iter/sec",
            "range": "stddev: 0.023388411640690016",
            "extra": "mean: 398.2082633999994 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 45.43468292565291,
            "unit": "iter/sec",
            "range": "stddev: 0.01165784343746642",
            "extra": "mean: 22.00961766667 msec\nrounds: 21"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 14.808980633363209,
            "unit": "iter/sec",
            "range": "stddev: 0.01681042448640921",
            "extra": "mean: 67.52659246154298 msec\nrounds: 13"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 6.451538737287149,
            "unit": "iter/sec",
            "range": "stddev: 0.003146188765222596",
            "extra": "mean: 155.00178185715998 msec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 3.076272993234796,
            "unit": "iter/sec",
            "range": "stddev: 0.035079886916250164",
            "extra": "mean: 325.0686796000082 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 47.12712866563669,
            "unit": "iter/sec",
            "range": "stddev: 0.010746065327299409",
            "extra": "mean: 21.219200666667433 msec\nrounds: 21"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 448407.42220790236,
            "unit": "iter/sec",
            "range": "stddev: 4.1348507987772754e-7",
            "extra": "mean: 2.2301147360053153 usec\nrounds: 78162"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1454131.4823805944,
            "unit": "iter/sec",
            "range": "stddev: 2.4495601280603754e-7",
            "extra": "mean: 687.6957222347427 nsec\nrounds: 119105"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 126.65640666016223,
            "unit": "iter/sec",
            "range": "stddev: 0.000049862091702534155",
            "extra": "mean: 7.895376367996506 msec\nrounds: 125"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3296558.076442655,
            "unit": "iter/sec",
            "range": "stddev: 9.155774355568097e-8",
            "extra": "mean: 303.34669579948934 nsec\nrounds: 192679"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4336223.496975811,
            "unit": "iter/sec",
            "range": "stddev: 3.8191216625177664e-8",
            "extra": "mean: 230.61541931531545 nsec\nrounds: 196890"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4099356.1765272003,
            "unit": "iter/sec",
            "range": "stddev: 3.033004261171179e-8",
            "extra": "mean: 243.94074506771875 nsec\nrounds: 194591"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 3937792.2476361524,
            "unit": "iter/sec",
            "range": "stddev: 3.310625435082222e-8",
            "extra": "mean: 253.94940543150736 nsec\nrounds: 194175"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3419767.2953140754,
            "unit": "iter/sec",
            "range": "stddev: 4.4861506233215464e-8",
            "extra": "mean: 292.41755758359545 nsec\nrounds: 189754"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 29469.001546898136,
            "unit": "iter/sec",
            "range": "stddev: 0.000003330270497443499",
            "extra": "mean: 33.933962723798444 usec\nrounds: 5419"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 29.935008551954986,
            "unit": "iter/sec",
            "range": "stddev: 0.00020668610564674215",
            "extra": "mean: 33.40570283333667 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 6554197.894413362,
            "unit": "iter/sec",
            "range": "stddev: 1.1412519102998493e-8",
            "extra": "mean: 152.57397108079016 nsec\nrounds: 66322"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 32250.05437195214,
            "unit": "iter/sec",
            "range": "stddev: 0.000003645569410526278",
            "extra": "mean: 31.007699660491106 usec\nrounds: 11477"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 32414.097254681947,
            "unit": "iter/sec",
            "range": "stddev: 0.000003562980811698594",
            "extra": "mean: 30.85077434496678 usec\nrounds: 13627"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 31891.08699897007,
            "unit": "iter/sec",
            "range": "stddev: 0.000003487986533032771",
            "extra": "mean: 31.356723589644194 usec\nrounds: 13404"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 215095.08062485777,
            "unit": "iter/sec",
            "range": "stddev: 7.744787876208933e-7",
            "extra": "mean: 4.649106790796747 usec\nrounds: 80756"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 216538.05578552754,
            "unit": "iter/sec",
            "range": "stddev: 7.438508804768817e-7",
            "extra": "mean: 4.618125882641436 usec\nrounds: 113431"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 214575.43814473844,
            "unit": "iter/sec",
            "range": "stddev: 7.679488269109572e-7",
            "extra": "mean: 4.660365644111913 usec\nrounds: 118681"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 179615.8675826636,
            "unit": "iter/sec",
            "range": "stddev: 0.0000017878921920461685",
            "extra": "mean: 5.567436849863922 usec\nrounds: 25004"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 223.33713595985483,
            "unit": "iter/sec",
            "range": "stddev: 0.00004164032010316692",
            "extra": "mean: 4.477535702704415 msec\nrounds: 222"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 31982.660400592704,
            "unit": "iter/sec",
            "range": "stddev: 0.0000035496936958555314",
            "extra": "mean: 31.266942382987878 usec\nrounds: 9702"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 32144.183917441347,
            "unit": "iter/sec",
            "range": "stddev: 0.0000036486843717927695",
            "extra": "mean: 31.109826977358807 usec\nrounds: 15917"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 32062.762190172136,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034343355633639974",
            "extra": "mean: 31.18882877491196 usec\nrounds: 15319"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 31943.049747972997,
            "unit": "iter/sec",
            "range": "stddev: 0.000003874397799494697",
            "extra": "mean: 31.305714635574418 usec\nrounds: 15128"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.3802467732388575,
            "unit": "iter/sec",
            "range": "stddev: 0.0010937810648874752",
            "extra": "mean: 295.8363892000193 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 26357.28045533366,
            "unit": "iter/sec",
            "range": "stddev: 0.0000038121716593666356",
            "extra": "mean: 37.94018133603158 usec\nrounds: 9612"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 25709.92695000566,
            "unit": "iter/sec",
            "range": "stddev: 0.000007805875342649074",
            "extra": "mean: 38.89548196478947 usec\nrounds: 13640"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 26001.413443568388,
            "unit": "iter/sec",
            "range": "stddev: 0.000006349674894484513",
            "extra": "mean: 38.459447682347296 usec\nrounds: 13418"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 169922.3135480921,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011394861905357968",
            "extra": "mean: 5.8850422826721696 usec\nrounds: 30911"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 18853.730619281083,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034555712255723043",
            "extra": "mean: 53.03990070683058 usec\nrounds: 12589"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1888.1023095636856,
            "unit": "iter/sec",
            "range": "stddev: 0.00001771527334545474",
            "extra": "mean: 529.6323164982973 usec\nrounds: 1782"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 199524.19040332633,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010534410541688077",
            "extra": "mean: 5.011923606749433 usec\nrounds: 26717"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 3231.2668478670253,
            "unit": "iter/sec",
            "range": "stddev: 0.00001013504885889753",
            "extra": "mean: 309.47614266525363 usec\nrounds: 2229"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 418.8901257474115,
            "unit": "iter/sec",
            "range": "stddev: 0.0009255068559771717",
            "extra": "mean: 2.387260855613948 msec\nrounds: 935"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 354.34362325670565,
            "unit": "iter/sec",
            "range": "stddev: 0.002011370980296609",
            "extra": "mean: 2.822119362016982 msec\nrounds: 337"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 48822.47711423779,
            "unit": "iter/sec",
            "range": "stddev: 0.000001681440815825582",
            "extra": "mean: 20.4823691690231 usec\nrounds: 16678"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 29.819650572299043,
            "unit": "iter/sec",
            "range": "stddev: 0.00021715199958180257",
            "extra": "mean: 33.534933535705136 msec\nrounds: 28"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 22220.2420123045,
            "unit": "iter/sec",
            "range": "stddev: 0.0000039936043438403595",
            "extra": "mean: 45.004010282437434 usec\nrounds: 9142"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 8421.296272739146,
            "unit": "iter/sec",
            "range": "stddev: 0.000006681821908321969",
            "extra": "mean: 118.74656437835262 usec\nrounds: 5957"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 12313.990143151299,
            "unit": "iter/sec",
            "range": "stddev: 0.000004081320192213832",
            "extra": "mean: 81.2084457088974 usec\nrounds: 9928"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3732.0389638344095,
            "unit": "iter/sec",
            "range": "stddev: 0.00010910579944502085",
            "extra": "mean: 267.95004277569757 usec\nrounds: 2104"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 2111947.4801493073,
            "unit": "iter/sec",
            "range": "stddev: 3.722877134777917e-8",
            "extra": "mean: 473.4966230927786 nsec\nrounds: 50564"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1905418.6581445632,
            "unit": "iter/sec",
            "range": "stddev: 7.097558223105787e-8",
            "extra": "mean: 524.8190447414684 nsec\nrounds: 175408"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "jaepil@cognica.io",
            "name": "Jaepil Jeong",
            "username": "jaepil"
          },
          "committer": {
            "email": "jaepil@cognica.io",
            "name": "Jaepil Jeong",
            "username": "jaepil"
          },
          "distinct": true,
          "id": "7a5b3a61c2227e343e69a85f02faddb8ef2fa2ad",
          "message": "Bump version to 0.11.0",
          "timestamp": "2026-03-12T16:56:39+09:00",
          "tree_id": "ca6787340e54704ce2299b8eb8d1e4827b2a3f3b",
          "url": "https://github.com/cognica-io/uqa/commit/7a5b3a61c2227e343e69a85f02faddb8ef2fa2ad"
        },
        "date": 1773302641178,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 18107.892658883513,
            "unit": "iter/sec",
            "range": "stddev: 0.000004472689933718202",
            "extra": "mean: 55.22453765537494 usec\nrounds: 3054"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 5894.743641154585,
            "unit": "iter/sec",
            "range": "stddev: 0.000010775692278000827",
            "extra": "mean: 169.64266147528906 usec\nrounds: 3403"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 8694.519557871343,
            "unit": "iter/sec",
            "range": "stddev: 0.000029392215417483286",
            "extra": "mean: 115.01498079841315 usec\nrounds: 5260"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 3844.614075656135,
            "unit": "iter/sec",
            "range": "stddev: 0.000016551477250854343",
            "extra": "mean: 260.1041301731531 usec\nrounds: 2658"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 8690.341265320898,
            "unit": "iter/sec",
            "range": "stddev: 0.0000068009432166216185",
            "extra": "mean: 115.07027968976706 usec\nrounds: 5928"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 4548.851415009233,
            "unit": "iter/sec",
            "range": "stddev: 0.00008881411927880486",
            "extra": "mean: 219.83571428612385 usec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 1535.8841288863637,
            "unit": "iter/sec",
            "range": "stddev: 0.00003269629821197238",
            "extra": "mean: 651.0907829518874 usec\nrounds: 1267"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4086.5701536284887,
            "unit": "iter/sec",
            "range": "stddev: 0.00002942999023595797",
            "extra": "mean: 244.7039846146026 usec\nrounds: 65"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 5191.91471689847,
            "unit": "iter/sec",
            "range": "stddev: 0.000016664945572554807",
            "extra": "mean: 192.6071699030867 usec\nrounds: 206"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 3854.4125602374097,
            "unit": "iter/sec",
            "range": "stddev: 0.00001164524359229289",
            "extra": "mean: 259.4429071542891 usec\nrounds: 3145"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 9388.236100217679,
            "unit": "iter/sec",
            "range": "stddev: 0.000012384507476338098",
            "extra": "mean: 106.51628158103243 usec\nrounds: 5288"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 6982.339246408937,
            "unit": "iter/sec",
            "range": "stddev: 0.000029977137214125263",
            "extra": "mean: 143.2184780357538 usec\nrounds: 4826"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 5957.521548237161,
            "unit": "iter/sec",
            "range": "stddev: 0.000040584683254498243",
            "extra": "mean: 167.8550370155021 usec\nrounds: 3431"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 5501.526556297687,
            "unit": "iter/sec",
            "range": "stddev: 0.00001535717865598017",
            "extra": "mean: 181.76773115005392 usec\nrounds: 3939"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 3291.740749652818,
            "unit": "iter/sec",
            "range": "stddev: 0.000015949407802158208",
            "extra": "mean: 303.7906311745452 usec\nrounds: 911"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1273.6448802695597,
            "unit": "iter/sec",
            "range": "stddev: 0.000057933935461509954",
            "extra": "mean: 785.1482116336508 usec\nrounds: 808"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 8476.88980848193,
            "unit": "iter/sec",
            "range": "stddev: 0.00000803072283610607",
            "extra": "mean: 117.96779509855199 usec\nrounds: 5427"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 7492.250787621276,
            "unit": "iter/sec",
            "range": "stddev: 0.000008662617281536854",
            "extra": "mean: 133.47123959761248 usec\nrounds: 5864"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 3245.815316450802,
            "unit": "iter/sec",
            "range": "stddev: 0.00001958655668046244",
            "extra": "mean: 308.0890015311989 usec\nrounds: 1959"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 4790.380517244294,
            "unit": "iter/sec",
            "range": "stddev: 0.000015883464969905223",
            "extra": "mean: 208.75168400510657 usec\nrounds: 3076"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 3272.6258231288184,
            "unit": "iter/sec",
            "range": "stddev: 0.00001512378883107901",
            "extra": "mean: 305.5650276095244 usec\nrounds: 2644"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1719.0438420470657,
            "unit": "iter/sec",
            "range": "stddev: 0.000017881151879184404",
            "extra": "mean: 581.7187296451866 usec\nrounds: 958"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1437.6368579072123,
            "unit": "iter/sec",
            "range": "stddev: 0.000017284037760776977",
            "extra": "mean: 695.5859503043862 usec\nrounds: 986"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1620.451655246161,
            "unit": "iter/sec",
            "range": "stddev: 0.000380819703422509",
            "extra": "mean: 617.1119001066966 usec\nrounds: 6557"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 1195.065892209689,
            "unit": "iter/sec",
            "range": "stddev: 0.000035868128673243924",
            "extra": "mean: 836.773944029973 usec\nrounds: 804"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 954.2510002542377,
            "unit": "iter/sec",
            "range": "stddev: 0.0001263362531951931",
            "extra": "mean: 1.0479423125923613 msec\nrounds: 675"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 98.96743828396993,
            "unit": "iter/sec",
            "range": "stddev: 0.0020648089787738697",
            "extra": "mean: 10.104333479165875 msec\nrounds: 96"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 99.36060560189955,
            "unit": "iter/sec",
            "range": "stddev: 0.0027886306439082616",
            "extra": "mean: 10.06435089583313 msec\nrounds: 96"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 145.13801200501157,
            "unit": "iter/sec",
            "range": "stddev: 0.004024643017785789",
            "extra": "mean: 6.889993780302505 msec\nrounds: 132"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 164.81251059972936,
            "unit": "iter/sec",
            "range": "stddev: 0.003212969506422804",
            "extra": "mean: 6.067500557822593 msec\nrounds: 147"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 82.56638512444272,
            "unit": "iter/sec",
            "range": "stddev: 0.003028486852492788",
            "extra": "mean: 12.111466409638936 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 59.76852906975753,
            "unit": "iter/sec",
            "range": "stddev: 0.0031995511561966937",
            "extra": "mean: 16.731213157895723 msec\nrounds: 57"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 241.0980063149079,
            "unit": "iter/sec",
            "range": "stddev: 0.00006344221068025955",
            "extra": "mean: 4.147690871793686 msec\nrounds: 39"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 73.33197792371807,
            "unit": "iter/sec",
            "range": "stddev: 0.00375352259524099",
            "extra": "mean: 13.636615680000167 msec\nrounds: 75"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10155118037172847,
            "unit": "iter/sec",
            "range": "stddev: 0.19847730751464682",
            "extra": "mean: 9.847251369600002 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 12.888911962905317,
            "unit": "iter/sec",
            "range": "stddev: 0.0008423212961369796",
            "extra": "mean: 77.58606800000113 msec\nrounds: 13"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 18.154005428179744,
            "unit": "iter/sec",
            "range": "stddev: 0.008844178930895653",
            "extra": "mean: 55.08426247618829 msec\nrounds: 21"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 65.71636429251679,
            "unit": "iter/sec",
            "range": "stddev: 0.004646400206494592",
            "extra": "mean: 15.216909985293746 msec\nrounds: 68"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 156.63225486009043,
            "unit": "iter/sec",
            "range": "stddev: 0.002622936725443043",
            "extra": "mean: 6.384381051611854 msec\nrounds: 155"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 127.74219284168888,
            "unit": "iter/sec",
            "range": "stddev: 0.0022511021510802872",
            "extra": "mean: 7.828267056909706 msec\nrounds: 123"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 323.95372949831034,
            "unit": "iter/sec",
            "range": "stddev: 0.000040343259131682925",
            "extra": "mean: 3.086860588234764 msec\nrounds: 289"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 1801.9069157464737,
            "unit": "iter/sec",
            "range": "stddev: 0.000017246833357743223",
            "extra": "mean: 554.9676241659415 usec\nrounds: 1349"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 446.9783780657108,
            "unit": "iter/sec",
            "range": "stddev: 0.001628012788427669",
            "extra": "mean: 2.2372446835739086 msec\nrounds: 414"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 219.2841517893635,
            "unit": "iter/sec",
            "range": "stddev: 0.0033902655118369204",
            "extra": "mean: 4.560293080188322 msec\nrounds: 212"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 197.09297817797608,
            "unit": "iter/sec",
            "range": "stddev: 0.0035088139195713843",
            "extra": "mean: 5.073747473118978 msec\nrounds: 186"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1565.8480032037637,
            "unit": "iter/sec",
            "range": "stddev: 0.000020878110119105067",
            "extra": "mean: 638.6315900099979 usec\nrounds: 961"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 113.73523219781357,
            "unit": "iter/sec",
            "range": "stddev: 0.00541116896877343",
            "extra": "mean: 8.792350274194314 msec\nrounds: 124"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 205.53743792060254,
            "unit": "iter/sec",
            "range": "stddev: 0.0041392838870194255",
            "extra": "mean: 4.8652936911001685 msec\nrounds: 191"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 63.752121120004674,
            "unit": "iter/sec",
            "range": "stddev: 0.004978898221325209",
            "extra": "mean: 15.685752606060532 msec\nrounds: 66"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 78.40961227934254,
            "unit": "iter/sec",
            "range": "stddev: 0.004627218478816968",
            "extra": "mean: 12.75353838554123 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 75.21532065177011,
            "unit": "iter/sec",
            "range": "stddev: 0.004862621685324226",
            "extra": "mean: 13.295163689187385 msec\nrounds: 74"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 84.98010216402702,
            "unit": "iter/sec",
            "range": "stddev: 0.0021391396669937623",
            "extra": "mean: 11.767460552940012 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 99.55257347652582,
            "unit": "iter/sec",
            "range": "stddev: 0.0036031675945992795",
            "extra": "mean: 10.044943742572329 msec\nrounds: 101"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 91.59067811286128,
            "unit": "iter/sec",
            "range": "stddev: 0.003864198586531919",
            "extra": "mean: 10.918141677778218 msec\nrounds: 90"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 75.98211809859082,
            "unit": "iter/sec",
            "range": "stddev: 0.006358926434047982",
            "extra": "mean: 13.160991362499885 msec\nrounds: 80"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 159.26647504178234,
            "unit": "iter/sec",
            "range": "stddev: 0.0037169775124584314",
            "extra": "mean: 6.2787852857147595 msec\nrounds: 140"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 152.7238407521206,
            "unit": "iter/sec",
            "range": "stddev: 0.0038242938981191956",
            "extra": "mean: 6.547766184213875 msec\nrounds: 38"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 165.37181074779411,
            "unit": "iter/sec",
            "range": "stddev: 0.00008033308542679967",
            "extra": "mean: 6.0469798055551545 msec\nrounds: 36"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 136.6569524548687,
            "unit": "iter/sec",
            "range": "stddev: 0.002031860696787025",
            "extra": "mean: 7.317593302325782 msec\nrounds: 129"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 38.049230986790306,
            "unit": "iter/sec",
            "range": "stddev: 0.00022210056964569948",
            "extra": "mean: 26.28174010526451 msec\nrounds: 38"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 217.6534874548813,
            "unit": "iter/sec",
            "range": "stddev: 0.0031632344407918115",
            "extra": "mean: 4.594458888269806 msec\nrounds: 179"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 206.2240838822462,
            "unit": "iter/sec",
            "range": "stddev: 0.003984737992211027",
            "extra": "mean: 4.84909415609769 msec\nrounds: 205"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 52.08954859315558,
            "unit": "iter/sec",
            "range": "stddev: 0.00501937799997375",
            "extra": "mean: 19.19770908000146 msec\nrounds: 25"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 86.73979503789266,
            "unit": "iter/sec",
            "range": "stddev: 0.004374586573470828",
            "extra": "mean: 11.528733720931038 msec\nrounds: 86"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 614617.063021329,
            "unit": "iter/sec",
            "range": "stddev: 3.7564443210061325e-7",
            "extra": "mean: 1.6270293491108252 usec\nrounds: 59627"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 256269.4535992236,
            "unit": "iter/sec",
            "range": "stddev: 6.341245218528659e-7",
            "extra": "mean: 3.9021427874267323 usec\nrounds: 57330"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 76562.22407486902,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012279938759220899",
            "extra": "mean: 13.061271561574744 usec\nrounds: 29323"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 760277.3974681933,
            "unit": "iter/sec",
            "range": "stddev: 3.316495656344548e-7",
            "extra": "mean: 1.3153093901385327 usec\nrounds: 106975"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2136228.6144607384,
            "unit": "iter/sec",
            "range": "stddev: 4.780729123418004e-8",
            "extra": "mean: 468.1146920468699 nsec\nrounds: 103328"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1399120.0283016863,
            "unit": "iter/sec",
            "range": "stddev: 2.479769680035174e-7",
            "extra": "mean: 714.7349618129934 nsec\nrounds: 183117"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2407733.1764843473,
            "unit": "iter/sec",
            "range": "stddev: 4.429551100525863e-8",
            "extra": "mean: 415.3284133668626 nsec\nrounds: 114601"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 170961.0068354571,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010816242251203111",
            "extra": "mean: 5.849287030477415 usec\nrounds: 85092"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1614.615284683061,
            "unit": "iter/sec",
            "range": "stddev: 0.00001543241447969115",
            "extra": "mean: 619.3425824011655 usec\nrounds: 1341"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1627.0454179073752,
            "unit": "iter/sec",
            "range": "stddev: 0.00001195108591735225",
            "extra": "mean: 614.6109930269496 usec\nrounds: 1434"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 447752.33755490923,
            "unit": "iter/sec",
            "range": "stddev: 9.268421191976671e-7",
            "extra": "mean: 2.233377508335994 usec\nrounds: 61196"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 197775.73020706754,
            "unit": "iter/sec",
            "range": "stddev: 8.105820108939318e-7",
            "extra": "mean: 5.056232121873692 usec\nrounds: 62898"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 117929.0085876961,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011033595271742342",
            "extra": "mean: 8.47967783309537 usec\nrounds: 47941"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 333610.1975785706,
            "unit": "iter/sec",
            "range": "stddev: 7.368155925493376e-7",
            "extra": "mean: 2.997510289728131 usec\nrounds: 97476"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 103621.39495504067,
            "unit": "iter/sec",
            "range": "stddev: 0.000001131179273302079",
            "extra": "mean: 9.650516675961375 usec\nrounds: 46534"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 16080.388288123151,
            "unit": "iter/sec",
            "range": "stddev: 0.000003730013516707648",
            "extra": "mean: 62.187553066650274 usec\nrounds: 6473"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 10368.158084219083,
            "unit": "iter/sec",
            "range": "stddev: 0.000006090474240674625",
            "extra": "mean: 96.44914669289776 usec\nrounds: 7635"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 12598.471568284633,
            "unit": "iter/sec",
            "range": "stddev: 0.000005920677734870546",
            "extra": "mean: 79.3747078429258 usec\nrounds: 8071"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 92011.71137636187,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012003286915701419",
            "extra": "mean: 10.868181724276717 usec\nrounds: 28070"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 25959.577559374382,
            "unit": "iter/sec",
            "range": "stddev: 0.000021347585768155963",
            "extra": "mean: 38.521428082287315 usec\nrounds: 12556"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 5884.952283472055,
            "unit": "iter/sec",
            "range": "stddev: 0.00002628281812065215",
            "extra": "mean: 169.92491218807493 usec\nrounds: 4168"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2090.574663502268,
            "unit": "iter/sec",
            "range": "stddev: 0.000013528092732845132",
            "extra": "mean: 478.3373765396804 usec\nrounds: 1543"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 90237.52694636033,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011801279881938727",
            "extra": "mean: 11.081863985417371 usec\nrounds: 35930"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 17756.36744633549,
            "unit": "iter/sec",
            "range": "stddev: 0.000002956219759211159",
            "extra": "mean: 56.31782531096343 usec\nrounds: 11260"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1296.340876873072,
            "unit": "iter/sec",
            "range": "stddev: 0.000010763757630237776",
            "extra": "mean: 771.4020423487059 usec\nrounds: 1039"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 180.80433978244892,
            "unit": "iter/sec",
            "range": "stddev: 0.000049004862629477046",
            "extra": "mean: 5.530840693333137 msec\nrounds: 150"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.3915817875132689,
            "unit": "iter/sec",
            "range": "stddev: 0.03925954576311521",
            "extra": "mean: 2.5537449184000023 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 71940.20450066244,
            "unit": "iter/sec",
            "range": "stddev: 0.000001398351266689716",
            "extra": "mean: 13.900433101921356 usec\nrounds: 25509"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 6480.097671078378,
            "unit": "iter/sec",
            "range": "stddev: 0.0000056572456526379715",
            "extra": "mean: 154.3186616558491 usec\nrounds: 4457"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 154.5905909433334,
            "unit": "iter/sec",
            "range": "stddev: 0.00004303918539175324",
            "extra": "mean: 6.4686989932431205 msec\nrounds: 148"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 71466.51168100454,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013691174992202491",
            "extra": "mean: 13.992567658311986 usec\nrounds: 28873"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 14639.960710484116,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034133828402605183",
            "extra": "mean: 68.30619424298523 usec\nrounds: 8963"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 2703.962191386858,
            "unit": "iter/sec",
            "range": "stddev: 0.000010685497388601147",
            "extra": "mean: 369.8276563131607 usec\nrounds: 1996"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 787.6646950615451,
            "unit": "iter/sec",
            "range": "stddev: 0.00009686064271018594",
            "extra": "mean: 1.2695757551020663 msec\nrounds: 637"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6159.036363280758,
            "unit": "iter/sec",
            "range": "stddev: 0.000005824282166227145",
            "extra": "mean: 162.36306152726235 usec\nrounds: 4177"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1334.5942059135878,
            "unit": "iter/sec",
            "range": "stddev: 0.000011796801748215424",
            "extra": "mean: 749.2914292366919 usec\nrounds: 1074"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 156.48840190606884,
            "unit": "iter/sec",
            "range": "stddev: 0.000054055631372102424",
            "extra": "mean: 6.390249934306592 msec\nrounds: 137"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 2714.483300207642,
            "unit": "iter/sec",
            "range": "stddev: 0.000008388492569495446",
            "extra": "mean: 368.3942354419737 usec\nrounds: 1992"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 52.75231448441615,
            "unit": "iter/sec",
            "range": "stddev: 0.00020738313859349245",
            "extra": "mean: 18.956514226412104 msec\nrounds: 53"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1245.8594608873784,
            "unit": "iter/sec",
            "range": "stddev: 0.000016697585330032693",
            "extra": "mean: 802.6587519652801 usec\nrounds: 1145"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 403.3304628204133,
            "unit": "iter/sec",
            "range": "stddev: 0.000019299607558599967",
            "extra": "mean: 2.4793564884913226 msec\nrounds: 391"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1474.7946155618924,
            "unit": "iter/sec",
            "range": "stddev: 0.000013321357920465623",
            "extra": "mean: 678.060517341259 usec\nrounds: 1384"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 493.5430338296399,
            "unit": "iter/sec",
            "range": "stddev: 0.000017945042122099325",
            "extra": "mean: 2.0261657676343128 msec\nrounds: 482"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 347.6723847572985,
            "unit": "iter/sec",
            "range": "stddev: 0.00003497457811144931",
            "extra": "mean: 2.8762710063903274 msec\nrounds: 313"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1594.4052070489115,
            "unit": "iter/sec",
            "range": "stddev: 0.00002727823725118673",
            "extra": "mean: 627.1931348310776 usec\nrounds: 979"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1258.3960296105631,
            "unit": "iter/sec",
            "range": "stddev: 0.000016454379260537386",
            "extra": "mean: 794.6623928156154 usec\nrounds: 863"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 851.5605073843101,
            "unit": "iter/sec",
            "range": "stddev: 0.0013217656946287162",
            "extra": "mean: 1.17431467444591 msec\nrounds: 857"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 65.77411860082725,
            "unit": "iter/sec",
            "range": "stddev: 0.010530150140370977",
            "extra": "mean: 15.203548466667296 msec\nrounds: 75"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 5.665506275848093,
            "unit": "iter/sec",
            "range": "stddev: 0.0457810442025743",
            "extra": "mean: 176.5067323749996 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 266.59560514846015,
            "unit": "iter/sec",
            "range": "stddev: 0.00007287976251649579",
            "extra": "mean: 3.7509995689656104 msec\nrounds: 232"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 62.80273949746615,
            "unit": "iter/sec",
            "range": "stddev: 0.011108598496105083",
            "extra": "mean: 15.922872282352369 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 32.271537015315474,
            "unit": "iter/sec",
            "range": "stddev: 0.015201038528399479",
            "extra": "mean: 30.987058333336236 msec\nrounds: 18"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 22.089652759322863,
            "unit": "iter/sec",
            "range": "stddev: 0.018005297505906025",
            "extra": "mean: 45.27006426472473 msec\nrounds: 34"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 881.0188598726036,
            "unit": "iter/sec",
            "range": "stddev: 0.001585423799577998",
            "extra": "mean: 1.1350494813977097 msec\nrounds: 887"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 65.37438693021126,
            "unit": "iter/sec",
            "range": "stddev: 0.010536858215631884",
            "extra": "mean: 15.29651055951812 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 5.605578409852874,
            "unit": "iter/sec",
            "range": "stddev: 0.04766669975515615",
            "extra": "mean: 178.3937226250032 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 273.33430670327584,
            "unit": "iter/sec",
            "range": "stddev: 0.00015183644199900532",
            "extra": "mean: 3.6585235569626917 msec\nrounds: 237"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 63.573482093847055,
            "unit": "iter/sec",
            "range": "stddev: 0.01162660611881684",
            "extra": "mean: 15.72982896428108 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 28.466586999068,
            "unit": "iter/sec",
            "range": "stddev: 0.019323974418724674",
            "extra": "mean: 35.12890393332858 msec\nrounds: 15"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 21.5237706626418,
            "unit": "iter/sec",
            "range": "stddev: 0.01967183570714071",
            "extra": "mean: 46.46026087499955 msec\nrounds: 32"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 15982.235288421536,
            "unit": "iter/sec",
            "range": "stddev: 0.0000032905936553579467",
            "extra": "mean: 62.569470537357084 usec\nrounds: 10437"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 964.8352105695263,
            "unit": "iter/sec",
            "range": "stddev: 0.000022555593032586064",
            "extra": "mean: 1.0364464201194692 msec\nrounds: 676"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 52.54535784045941,
            "unit": "iter/sec",
            "range": "stddev: 0.0025363186136005706",
            "extra": "mean: 19.031176893613424 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1080.0996066090054,
            "unit": "iter/sec",
            "range": "stddev: 0.0000136283226196326",
            "extra": "mean: 925.8405371885285 usec\nrounds: 605"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 963.9255406649467,
            "unit": "iter/sec",
            "range": "stddev: 0.00002802807412513117",
            "extra": "mean: 1.037424528984021 msec\nrounds: 414"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 909.9917133719479,
            "unit": "iter/sec",
            "range": "stddev: 0.000025232651292729395",
            "extra": "mean: 1.098911105788567 msec\nrounds: 501"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 884.4423060598415,
            "unit": "iter/sec",
            "range": "stddev: 0.0001364319846614467",
            "extra": "mean: 1.130655999999552 msec\nrounds: 695"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 148.85415825488073,
            "unit": "iter/sec",
            "range": "stddev: 0.00031565877874196064",
            "extra": "mean: 6.717984984253614 msec\nrounds: 127"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 141.5555286490292,
            "unit": "iter/sec",
            "range": "stddev: 0.00021825422962974447",
            "extra": "mean: 7.064365549998304 msec\nrounds: 120"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 89.03335223930391,
            "unit": "iter/sec",
            "range": "stddev: 0.000476505555531757",
            "extra": "mean: 11.231746023806892 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 55.93892766882459,
            "unit": "iter/sec",
            "range": "stddev: 0.013519035519622857",
            "extra": "mean: 17.876638714283246 msec\nrounds: 77"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 15.722594437479067,
            "unit": "iter/sec",
            "range": "stddev: 0.023372667490716786",
            "extra": "mean: 63.602734521742086 msec\nrounds: 23"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 5.7614089364238765,
            "unit": "iter/sec",
            "range": "stddev: 0.029382617060217994",
            "extra": "mean: 173.5686549999874 msec\nrounds: 6"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.029504488957734,
            "unit": "iter/sec",
            "range": "stddev: 0.013324407235517198",
            "extra": "mean: 492.73111019998623 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 41.154898744519194,
            "unit": "iter/sec",
            "range": "stddev: 0.014419592083116137",
            "extra": "mean: 24.29844393999815 msec\nrounds: 50"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 13.41694713967358,
            "unit": "iter/sec",
            "range": "stddev: 0.025180333400982698",
            "extra": "mean: 74.53260339999588 msec\nrounds: 10"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 5.830131342606467,
            "unit": "iter/sec",
            "range": "stddev: 0.004182128030816617",
            "extra": "mean: 171.52272242857083 msec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 2.7648840895088886,
            "unit": "iter/sec",
            "range": "stddev: 0.03907117260936492",
            "extra": "mean: 361.678814600009 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 40.4227399363184,
            "unit": "iter/sec",
            "range": "stddev: 0.016197252225591038",
            "extra": "mean: 24.73855066666412 msec\nrounds: 18"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 441153.109920171,
            "unit": "iter/sec",
            "range": "stddev: 4.4828599997455195e-7",
            "extra": "mean: 2.2667866949435203 usec\nrounds: 70289"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1462436.7107016204,
            "unit": "iter/sec",
            "range": "stddev: 3.1064183108512195e-7",
            "extra": "mean: 683.7902746028843 nsec\nrounds: 102062"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 122.4259244471974,
            "unit": "iter/sec",
            "range": "stddev: 0.00016906094300285274",
            "extra": "mean: 8.168204606298909 msec\nrounds: 127"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3287208.659412344,
            "unit": "iter/sec",
            "range": "stddev: 1.0936048669992177e-7",
            "extra": "mean: 304.2094687651408 nsec\nrounds: 163881"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4325759.189081423,
            "unit": "iter/sec",
            "range": "stddev: 2.8764798376973818e-8",
            "extra": "mean: 231.17329381720634 nsec\nrounds: 196117"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4087431.4534290093,
            "unit": "iter/sec",
            "range": "stddev: 3.0843104296064307e-8",
            "extra": "mean: 244.65242081578754 nsec\nrounds: 191939"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 3931167.2958034175,
            "unit": "iter/sec",
            "range": "stddev: 5.995175133793241e-8",
            "extra": "mean: 254.37737057578693 nsec\nrounds: 196503"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3426444.8440886973,
            "unit": "iter/sec",
            "range": "stddev: 4.1026882432557706e-8",
            "extra": "mean: 291.8476863052969 nsec\nrounds: 199641"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 30005.598933799294,
            "unit": "iter/sec",
            "range": "stddev: 0.0000033131171972189602",
            "extra": "mean: 33.32711345660116 usec\nrounds: 5165"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 30.39036139622575,
            "unit": "iter/sec",
            "range": "stddev: 0.0002244901394950282",
            "extra": "mean: 32.90516973332842 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 6422944.737636214,
            "unit": "iter/sec",
            "range": "stddev: 1.2173591489627652e-8",
            "extra": "mean: 155.69182685635593 nsec\nrounds: 64986"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 32798.02705249658,
            "unit": "iter/sec",
            "range": "stddev: 0.0000037201567979081005",
            "extra": "mean: 30.489638855392066 usec\nrounds: 10835"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 32575.13535497629,
            "unit": "iter/sec",
            "range": "stddev: 0.0000039794906872601225",
            "extra": "mean: 30.698260777824718 usec\nrounds: 18951"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 32279.931487007078,
            "unit": "iter/sec",
            "range": "stddev: 0.000004049449191344087",
            "extra": "mean: 30.979000076332497 usec\nrounds: 13137"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 214976.89017723672,
            "unit": "iter/sec",
            "range": "stddev: 8.129529868215607e-7",
            "extra": "mean: 4.651662786523493 usec\nrounds: 73449"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 215381.46234377864,
            "unit": "iter/sec",
            "range": "stddev: 9.848058310335897e-7",
            "extra": "mean: 4.642925111186503 usec\nrounds: 108027"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 213473.7394925671,
            "unit": "iter/sec",
            "range": "stddev: 8.402637835725388e-7",
            "extra": "mean: 4.684416932860347 usec\nrounds: 115527"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 185962.86529573656,
            "unit": "iter/sec",
            "range": "stddev: 9.990850500665366e-7",
            "extra": "mean: 5.3774176818027675 usec\nrounds: 22577"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 222.19334247420957,
            "unit": "iter/sec",
            "range": "stddev: 0.00004664812047355138",
            "extra": "mean: 4.500584890909016 msec\nrounds: 220"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 32486.78977974514,
            "unit": "iter/sec",
            "range": "stddev: 0.000003829061017450065",
            "extra": "mean: 30.781742572283328 usec\nrounds: 9424"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 32683.43474213406,
            "unit": "iter/sec",
            "range": "stddev: 0.000003872683918582046",
            "extra": "mean: 30.596539436255874 usec\nrounds: 11601"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 32391.164829377867,
            "unit": "iter/sec",
            "range": "stddev: 0.0000039236171984394525",
            "extra": "mean: 30.872616198508194 usec\nrounds: 15026"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 32300.221386085494,
            "unit": "iter/sec",
            "range": "stddev: 0.0000037480319576223716",
            "extra": "mean: 30.95954012348617 usec\nrounds: 15228"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.388807421770086,
            "unit": "iter/sec",
            "range": "stddev: 0.005514851624365807",
            "extra": "mean: 295.08906100001013 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 26763.949190403004,
            "unit": "iter/sec",
            "range": "stddev: 0.000004534362150986836",
            "extra": "mean: 37.363693709244494 usec\nrounds: 10428"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 26698.71361405179,
            "unit": "iter/sec",
            "range": "stddev: 0.000004753333338170988",
            "extra": "mean: 37.454988073795825 usec\nrounds: 13332"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 26449.69016379338,
            "unit": "iter/sec",
            "range": "stddev: 0.000004920658686304063",
            "extra": "mean: 37.80762624466907 usec\nrounds: 13153"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 174524.3589538491,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012450693255573953",
            "extra": "mean: 5.729859178365114 usec\nrounds: 29761"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 19420.22058603705,
            "unit": "iter/sec",
            "range": "stddev: 0.000004511656415965585",
            "extra": "mean: 51.492720979646876 usec\nrounds: 12698"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1967.4072010834436,
            "unit": "iter/sec",
            "range": "stddev: 0.000016561293365258955",
            "extra": "mean: 508.28318583428165 usec\nrounds: 1878"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 200150.0947956403,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010707847204925338",
            "extra": "mean: 4.996250444053161 usec\nrounds: 24780"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 3253.234234901364,
            "unit": "iter/sec",
            "range": "stddev: 0.000008354571049990816",
            "extra": "mean: 307.3864123498379 usec\nrounds: 2413"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 425.98826841620854,
            "unit": "iter/sec",
            "range": "stddev: 0.0008965397440886259",
            "extra": "mean: 2.347482487529346 msec\nrounds: 882"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 357.9454366676426,
            "unit": "iter/sec",
            "range": "stddev: 0.0021071345632803556",
            "extra": "mean: 2.793721884848372 msec\nrounds: 330"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 48305.72475504729,
            "unit": "iter/sec",
            "range": "stddev: 0.0000018748631224392799",
            "extra": "mean: 20.70148010553374 usec\nrounds: 15557"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 29.301572546487726,
            "unit": "iter/sec",
            "range": "stddev: 0.0005147578550085817",
            "extra": "mean: 34.12786117241569 msec\nrounds: 29"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 22247.354371351572,
            "unit": "iter/sec",
            "range": "stddev: 0.0000041856634710924254",
            "extra": "mean: 44.94916488981372 usec\nrounds: 8630"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 8187.057340827037,
            "unit": "iter/sec",
            "range": "stddev: 0.000009153257486181545",
            "extra": "mean: 122.14400832558263 usec\nrounds: 5165"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 12202.962542928115,
            "unit": "iter/sec",
            "range": "stddev: 0.000004136732079114251",
            "extra": "mean: 81.94731373485385 usec\nrounds: 8402"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3560.22904291896,
            "unit": "iter/sec",
            "range": "stddev: 0.00011452836263052237",
            "extra": "mean: 280.88080512374006 usec\nrounds: 1991"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 2126580.009930343,
            "unit": "iter/sec",
            "range": "stddev: 4.103665881090513e-8",
            "extra": "mean: 470.23859686932514 nsec\nrounds: 51852"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1586054.4484513535,
            "unit": "iter/sec",
            "range": "stddev: 2.1792831801660453e-7",
            "extra": "mean: 630.4953786273949 nsec\nrounds: 185874"
          }
        ]
      }
    ]
  }
}