window.BENCHMARK_DATA = {
  "lastUpdate": 1773388985841,
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
          "id": "7b7600b2cdf0a66421444c19f27be8554324537f",
          "message": "Add public API methods and quickstart, remove private API exposure\n\nAdd get_document(), get_graph_store(), get_table_analyzer() to Engine\nas public accessors for per-table storage. Replace all _tables access\nin 8 example files with the new public methods. Add quickstart.py\ndemonstrating hybrid search in under 30 lines. Update README and API\nmanual documentation.",
          "timestamp": "2026-03-12T20:47:43+09:00",
          "tree_id": "5476093179e7260810b5ac6bdf55b3e81b686b11",
          "url": "https://github.com/cognica-io/uqa/commit/7b7600b2cdf0a66421444c19f27be8554324537f"
        },
        "date": 1773316388670,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 18097.915557344175,
            "unit": "iter/sec",
            "range": "stddev: 0.000004658021767027276",
            "extra": "mean: 55.254982090697055 usec\nrounds: 3071"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 5889.840792575824,
            "unit": "iter/sec",
            "range": "stddev: 0.00001402120034936147",
            "extra": "mean: 169.7838762060437 usec\nrounds: 3732"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 9101.87469365522,
            "unit": "iter/sec",
            "range": "stddev: 0.0000064623075160058815",
            "extra": "mean: 109.86747605930952 usec\nrounds: 5806"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 3806.8351188375477,
            "unit": "iter/sec",
            "range": "stddev: 0.000010059245300375422",
            "extra": "mean: 262.68539844335555 usec\nrounds: 2826"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 8687.21421598474,
            "unit": "iter/sec",
            "range": "stddev: 0.0000057038154923945244",
            "extra": "mean: 115.11170038376275 usec\nrounds: 5991"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 4289.39703962996,
            "unit": "iter/sec",
            "range": "stddev: 0.00008971609065573804",
            "extra": "mean: 233.13299999066265 usec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 1484.1116900539282,
            "unit": "iter/sec",
            "range": "stddev: 0.00003783151948647138",
            "extra": "mean: 673.8037350569371 usec\nrounds: 1238"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4082.877137647615,
            "unit": "iter/sec",
            "range": "stddev: 0.000027188574755204315",
            "extra": "mean: 244.9253225817514 usec\nrounds: 62"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 5060.109138120902,
            "unit": "iter/sec",
            "range": "stddev: 0.00001744096413462404",
            "extra": "mean: 197.62419598154267 usec\nrounds: 199"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 3799.452375274519,
            "unit": "iter/sec",
            "range": "stddev: 0.000011045965018462633",
            "extra": "mean: 263.1958243529102 usec\nrounds: 3285"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 9371.012355051429,
            "unit": "iter/sec",
            "range": "stddev: 0.00000688687775437293",
            "extra": "mean: 106.71205651126387 usec\nrounds: 5291"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 7151.541829931452,
            "unit": "iter/sec",
            "range": "stddev: 0.0000069153540787340264",
            "extra": "mean: 139.82998684489064 usec\nrounds: 5093"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 6063.822572333186,
            "unit": "iter/sec",
            "range": "stddev: 0.000012826518836184718",
            "extra": "mean: 164.9124769188668 usec\nrounds: 3466"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 5417.327938969379,
            "unit": "iter/sec",
            "range": "stddev: 0.00001112950868011446",
            "extra": "mean: 184.59284932826964 usec\nrounds: 4095"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 3264.8459780692506,
            "unit": "iter/sec",
            "range": "stddev: 0.000013708018555570703",
            "extra": "mean: 306.2931625924281 usec\nrounds: 941"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1337.5014681885034,
            "unit": "iter/sec",
            "range": "stddev: 0.00002295352371651958",
            "extra": "mean: 747.6627306842424 usec\nrounds: 906"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 9032.44257319651,
            "unit": "iter/sec",
            "range": "stddev: 0.000007902117518790238",
            "extra": "mean: 110.71202411709416 usec\nrounds: 5805"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 7991.281996462783,
            "unit": "iter/sec",
            "range": "stddev: 0.000007043137796603639",
            "extra": "mean: 125.13636741171624 usec\nrounds: 6309"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 3362.7960962884267,
            "unit": "iter/sec",
            "range": "stddev: 0.00001750810638863124",
            "extra": "mean: 297.371583458098 usec\nrounds: 2007"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 4964.70666462111,
            "unit": "iter/sec",
            "range": "stddev: 0.000013363399891115827",
            "extra": "mean: 201.42176921067235 usec\nrounds: 3839"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 3310.2384369954143,
            "unit": "iter/sec",
            "range": "stddev: 0.00029038863072544386",
            "extra": "mean: 302.093042248541 usec\nrounds: 2722"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1720.578798620385,
            "unit": "iter/sec",
            "range": "stddev: 0.00003737053485454278",
            "extra": "mean: 581.1997688230449 usec\nrounds: 943"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1429.3384210240479,
            "unit": "iter/sec",
            "range": "stddev: 0.000032183043026442964",
            "extra": "mean: 699.6243753690964 usec\nrounds: 1015"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1595.0865047721263,
            "unit": "iter/sec",
            "range": "stddev: 0.00034786371942835094",
            "extra": "mean: 626.9252463789478 usec\nrounds: 6904"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 1184.0531668558367,
            "unit": "iter/sec",
            "range": "stddev: 0.000046855402265824124",
            "extra": "mean: 844.55667025107 usec\nrounds: 837"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 953.3888623287642,
            "unit": "iter/sec",
            "range": "stddev: 0.000041509990494732754",
            "extra": "mean: 1.0488899540502106 msec\nrounds: 827"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 96.038311093545,
            "unit": "iter/sec",
            "range": "stddev: 0.0029331148879692273",
            "extra": "mean: 10.412511305264017 msec\nrounds: 95"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 97.84460554573877,
            "unit": "iter/sec",
            "range": "stddev: 0.0030535957506901816",
            "extra": "mean: 10.220287510204502 msec\nrounds: 98"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 156.21214523348294,
            "unit": "iter/sec",
            "range": "stddev: 0.002261254973167762",
            "extra": "mean: 6.401550906975555 msec\nrounds: 43"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 164.55702982640375,
            "unit": "iter/sec",
            "range": "stddev: 0.002864977180400001",
            "extra": "mean: 6.076920573098157 msec\nrounds: 171"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 84.2887996041576,
            "unit": "iter/sec",
            "range": "stddev: 0.0027092640719785536",
            "extra": "mean: 11.86397249333557 msec\nrounds: 75"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 60.432350926508164,
            "unit": "iter/sec",
            "range": "stddev: 0.0029469086986622177",
            "extra": "mean: 16.547428399998886 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 234.79351265038756,
            "unit": "iter/sec",
            "range": "stddev: 0.0013082771296852958",
            "extra": "mean: 4.259061456646892 msec\nrounds: 173"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 78.41137390351977,
            "unit": "iter/sec",
            "range": "stddev: 0.003268089395937878",
            "extra": "mean: 12.753251858976947 msec\nrounds: 78"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10687278595845401,
            "unit": "iter/sec",
            "range": "stddev: 0.034436112118409336",
            "extra": "mean: 9.356918985800018 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 12.683045950912257,
            "unit": "iter/sec",
            "range": "stddev: 0.00036860472333137746",
            "extra": "mean: 78.84541330768204 msec\nrounds: 13"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 18.32906724293168,
            "unit": "iter/sec",
            "range": "stddev: 0.008247201047870887",
            "extra": "mean: 54.55815000000257 msec\nrounds: 20"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 68.09518184159072,
            "unit": "iter/sec",
            "range": "stddev: 0.004303848394586202",
            "extra": "mean: 14.685326816900085 msec\nrounds: 71"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 166.68075049119233,
            "unit": "iter/sec",
            "range": "stddev: 0.0015292080446429913",
            "extra": "mean: 5.999493025157944 msec\nrounds: 159"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 139.72939414445466,
            "unit": "iter/sec",
            "range": "stddev: 0.0021824960886725813",
            "extra": "mean: 7.156690302157775 msec\nrounds: 139"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 339.0825844096493,
            "unit": "iter/sec",
            "range": "stddev: 0.00011985164888516339",
            "extra": "mean: 2.949134063434792 msec\nrounds: 268"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 1885.9885732374353,
            "unit": "iter/sec",
            "range": "stddev: 0.0000214388780432959",
            "extra": "mean: 530.2259060262639 usec\nrounds: 1394"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 463.9170668349031,
            "unit": "iter/sec",
            "range": "stddev: 0.0011952665622160187",
            "extra": "mean: 2.155557687977614 msec\nrounds: 391"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 222.76085635354423,
            "unit": "iter/sec",
            "range": "stddev: 0.0027726110793736465",
            "extra": "mean: 4.489119032712362 msec\nrounds: 214"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 199.4046509908101,
            "unit": "iter/sec",
            "range": "stddev: 0.003353719784961701",
            "extra": "mean: 5.014928162563704 msec\nrounds: 203"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1544.0681126604434,
            "unit": "iter/sec",
            "range": "stddev: 0.000021026392488043736",
            "extra": "mean: 647.6398235288927 usec\nrounds: 918"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 119.64613148516617,
            "unit": "iter/sec",
            "range": "stddev: 0.004299684157267359",
            "extra": "mean: 8.357980217053495 msec\nrounds: 129"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 216.17998872420898,
            "unit": "iter/sec",
            "range": "stddev: 0.0030556720133614315",
            "extra": "mean: 4.625775058558945 msec\nrounds: 222"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 71.46947539535353,
            "unit": "iter/sec",
            "range": "stddev: 0.003503453720597431",
            "extra": "mean: 13.99198741096417 msec\nrounds: 73"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 90.22946881935506,
            "unit": "iter/sec",
            "range": "stddev: 0.002640223219857423",
            "extra": "mean: 11.08285367391513 msec\nrounds: 92"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 81.55431261369625,
            "unit": "iter/sec",
            "range": "stddev: 0.004112387006407539",
            "extra": "mean: 12.261767256095537 msec\nrounds: 82"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 86.48255796564278,
            "unit": "iter/sec",
            "range": "stddev: 0.004021675662635838",
            "extra": "mean: 11.563025233334026 msec\nrounds: 90"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 102.70111955107012,
            "unit": "iter/sec",
            "range": "stddev: 0.003290748822876359",
            "extra": "mean: 9.736992199999637 msec\nrounds: 95"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 96.20120389277842,
            "unit": "iter/sec",
            "range": "stddev: 0.0032735519128932467",
            "extra": "mean: 10.394880308510022 msec\nrounds: 94"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 81.24258042797459,
            "unit": "iter/sec",
            "range": "stddev: 0.0052503140608233904",
            "extra": "mean: 12.308816321836892 msec\nrounds: 87"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 163.94324656690043,
            "unit": "iter/sec",
            "range": "stddev: 0.0030487230470783973",
            "extra": "mean: 6.099671812903433 msec\nrounds: 155"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 149.05572682224673,
            "unit": "iter/sec",
            "range": "stddev: 0.0037361433093194597",
            "extra": "mean: 6.70890023026441 msec\nrounds: 152"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 163.30100690327043,
            "unit": "iter/sec",
            "range": "stddev: 0.0018887441110920927",
            "extra": "mean: 6.123660955699673 msec\nrounds: 158"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 142.38497631055952,
            "unit": "iter/sec",
            "range": "stddev: 0.0013558050351436105",
            "extra": "mean: 7.023212883210896 msec\nrounds: 137"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 39.09303889151179,
            "unit": "iter/sec",
            "range": "stddev: 0.0008569018891733556",
            "extra": "mean: 25.580001666668295 msec\nrounds: 36"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 215.855629948313,
            "unit": "iter/sec",
            "range": "stddev: 0.0029421547934159863",
            "extra": "mean: 4.6327260504599845 msec\nrounds: 218"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 219.0053858873042,
            "unit": "iter/sec",
            "range": "stddev: 0.002914125149415255",
            "extra": "mean: 4.566097751196768 msec\nrounds: 209"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 54.35959369397064,
            "unit": "iter/sec",
            "range": "stddev: 0.00498008161444672",
            "extra": "mean: 18.396016821422936 msec\nrounds: 28"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 93.84840137330815,
            "unit": "iter/sec",
            "range": "stddev: 0.0032173757980969537",
            "extra": "mean: 10.65548251612962 msec\nrounds: 93"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 629119.9208900415,
            "unit": "iter/sec",
            "range": "stddev: 3.533259820712735e-7",
            "extra": "mean: 1.589522071698603 usec\nrounds: 59624"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 259947.09093973663,
            "unit": "iter/sec",
            "range": "stddev: 6.20569003560832e-7",
            "extra": "mean: 3.8469366838647536 usec\nrounds: 54994"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 76553.83153957245,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012144979429624375",
            "extra": "mean: 13.062703458324966 usec\nrounds: 28077"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 765699.412377629,
            "unit": "iter/sec",
            "range": "stddev: 3.24282005899383e-7",
            "extra": "mean: 1.3059955170852584 usec\nrounds: 99711"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2135562.795905577,
            "unit": "iter/sec",
            "range": "stddev: 4.978527415755992e-8",
            "extra": "mean: 468.26063926439303 nsec\nrounds: 105731"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1393120.2504945723,
            "unit": "iter/sec",
            "range": "stddev: 2.3652818499310888e-7",
            "extra": "mean: 717.8131246351415 nsec\nrounds: 186916"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2448819.205791334,
            "unit": "iter/sec",
            "range": "stddev: 4.4610383520931754e-8",
            "extra": "mean: 408.3600772303036 nsec\nrounds: 108378"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 170950.66836489245,
            "unit": "iter/sec",
            "range": "stddev: 7.938230343431208e-7",
            "extra": "mean: 5.849640773942517 usec\nrounds: 78040"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1589.4806702018752,
            "unit": "iter/sec",
            "range": "stddev: 0.00001759457820820685",
            "extra": "mean: 629.1363076928724 usec\nrounds: 1235"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1594.079933325545,
            "unit": "iter/sec",
            "range": "stddev: 0.000013382625699211467",
            "extra": "mean: 627.3211142642109 usec\nrounds: 1374"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 449004.71960204514,
            "unit": "iter/sec",
            "range": "stddev: 5.577375565815038e-7",
            "extra": "mean: 2.2271480818426683 usec\nrounds: 65842"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 194889.7891255496,
            "unit": "iter/sec",
            "range": "stddev: 8.02201611699817e-7",
            "extra": "mean: 5.1311051465902695 usec\nrounds: 60972"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 117809.36451832902,
            "unit": "iter/sec",
            "range": "stddev: 9.141660683327139e-7",
            "extra": "mean: 8.488289569242333 usec\nrounds: 50361"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 332936.1514251096,
            "unit": "iter/sec",
            "range": "stddev: 6.206239748324863e-7",
            "extra": "mean: 3.003578901598913 usec\nrounds: 101031"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 101000.87890057587,
            "unit": "iter/sec",
            "range": "stddev: 0.000001111707241293542",
            "extra": "mean: 9.900903941483408 usec\nrounds: 50209"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 15854.626966152522,
            "unit": "iter/sec",
            "range": "stddev: 0.000005134288050281395",
            "extra": "mean: 63.073070223277064 usec\nrounds: 6223"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 10360.050576532829,
            "unit": "iter/sec",
            "range": "stddev: 0.000005534008050340976",
            "extra": "mean: 96.52462530107333 usec\nrounds: 7889"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 12484.093969833828,
            "unit": "iter/sec",
            "range": "stddev: 0.000004691118028444642",
            "extra": "mean: 80.10192829502634 usec\nrounds: 8005"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 89422.93490364286,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011827271243922026",
            "extra": "mean: 11.182813459181853 usec\nrounds: 28991"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 25806.606175446894,
            "unit": "iter/sec",
            "range": "stddev: 0.000005466996173165398",
            "extra": "mean: 38.749767916070546 usec\nrounds: 12810"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 5971.8043899462145,
            "unit": "iter/sec",
            "range": "stddev: 0.000005477254408476944",
            "extra": "mean: 167.4535759549563 usec\nrounds: 3851"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2083.998199545387,
            "unit": "iter/sec",
            "range": "stddev: 0.000019161710274085703",
            "extra": "mean: 479.84686369601695 usec\nrounds: 1526"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 90478.36403586909,
            "unit": "iter/sec",
            "range": "stddev: 0.000001222524884144388",
            "extra": "mean: 11.05236606183067 usec\nrounds: 35647"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 17851.601436814595,
            "unit": "iter/sec",
            "range": "stddev: 0.00000319619639307369",
            "extra": "mean: 56.017383288523504 usec\nrounds: 11190"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1326.8895163295479,
            "unit": "iter/sec",
            "range": "stddev: 0.00001981919891861183",
            "extra": "mean: 753.6422495568493 usec\nrounds: 565"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 180.22743375116286,
            "unit": "iter/sec",
            "range": "stddev: 0.00014763836116959628",
            "extra": "mean: 5.548544853502626 msec\nrounds: 157"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.38210583225586164,
            "unit": "iter/sec",
            "range": "stddev: 0.013210214190681642",
            "extra": "mean: 2.6170759920000135 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 72272.93737666881,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013086320078303153",
            "extra": "mean: 13.836437763533057 usec\nrounds: 26343"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 6509.473108281624,
            "unit": "iter/sec",
            "range": "stddev: 0.000005935368477465077",
            "extra": "mean: 153.62226456205158 usec\nrounds: 4498"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 156.92623639180198,
            "unit": "iter/sec",
            "range": "stddev: 0.000168660929420992",
            "extra": "mean: 6.372420718121812 msec\nrounds: 149"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 71327.2339225987,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012656736551542924",
            "extra": "mean: 14.019890370137693 usec\nrounds: 28733"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 14755.892511402048,
            "unit": "iter/sec",
            "range": "stddev: 0.0000037830147881244112",
            "extra": "mean: 67.76953676148621 usec\nrounds: 9004"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 2653.086445457156,
            "unit": "iter/sec",
            "range": "stddev: 0.000017809488957011136",
            "extra": "mean: 376.9194937889364 usec\nrounds: 1932"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 777.7577223059873,
            "unit": "iter/sec",
            "range": "stddev: 0.00006022203171472847",
            "extra": "mean: 1.285747439491932 msec\nrounds: 628"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6015.71193326937,
            "unit": "iter/sec",
            "range": "stddev: 0.000006717880122277333",
            "extra": "mean: 166.23136398363548 usec\nrounds: 4187"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1314.6739379977002,
            "unit": "iter/sec",
            "range": "stddev: 0.000024792349710819435",
            "extra": "mean: 760.6448801465092 usec\nrounds: 1093"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 158.41081768189383,
            "unit": "iter/sec",
            "range": "stddev: 0.00009256572940261953",
            "extra": "mean: 6.312700197079399 msec\nrounds: 137"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 2676.0915066515204,
            "unit": "iter/sec",
            "range": "stddev: 0.000008101244791802604",
            "extra": "mean: 373.6792996481864 usec\nrounds: 1989"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 53.03514029675414,
            "unit": "iter/sec",
            "range": "stddev: 0.00035474869780838806",
            "extra": "mean: 18.855422921568138 msec\nrounds: 51"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1216.1354572343494,
            "unit": "iter/sec",
            "range": "stddev: 0.00003718266738232611",
            "extra": "mean: 822.2768229076476 usec\nrounds: 1135"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 396.49495050892097,
            "unit": "iter/sec",
            "range": "stddev: 0.000054300141218323824",
            "extra": "mean: 2.5221002151892487 msec\nrounds: 395"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1455.3212858825411,
            "unit": "iter/sec",
            "range": "stddev: 0.000015556660689264177",
            "extra": "mean: 687.133493958055 usec\nrounds: 1407"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 481.7815899479157,
            "unit": "iter/sec",
            "range": "stddev: 0.00004244073664369507",
            "extra": "mean: 2.075629332594688 msec\nrounds: 451"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 341.92260682056184,
            "unit": "iter/sec",
            "range": "stddev: 0.00013058693521399996",
            "extra": "mean: 2.924638441718455 msec\nrounds: 326"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1583.8264947262874,
            "unit": "iter/sec",
            "range": "stddev: 0.00001990948849075584",
            "extra": "mean: 631.3822905032393 usec\nrounds: 1074"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1233.7315708998929,
            "unit": "iter/sec",
            "range": "stddev: 0.000025549136180895007",
            "extra": "mean: 810.5490883001338 usec\nrounds: 906"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 848.2585334131584,
            "unit": "iter/sec",
            "range": "stddev: 0.0014169232613955752",
            "extra": "mean: 1.17888587100477 msec\nrounds: 876"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 64.98373237047771,
            "unit": "iter/sec",
            "range": "stddev: 0.01075904536416476",
            "extra": "mean: 15.388466674996693 msec\nrounds: 80"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 5.961445827549607,
            "unit": "iter/sec",
            "range": "stddev: 0.04595065351396102",
            "extra": "mean: 167.7445419999799 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 257.5307808023736,
            "unit": "iter/sec",
            "range": "stddev: 0.00014591155458260164",
            "extra": "mean: 3.883030979381798 msec\nrounds: 194"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 64.59630922850326,
            "unit": "iter/sec",
            "range": "stddev: 0.010799703245995123",
            "extra": "mean: 15.480760618421646 msec\nrounds: 76"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 30.409779913882367,
            "unit": "iter/sec",
            "range": "stddev: 0.016970248577520105",
            "extra": "mean: 32.88415775556107 msec\nrounds: 45"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 22.844554240745115,
            "unit": "iter/sec",
            "range": "stddev: 0.017028686784521376",
            "extra": "mean: 43.7741086764748 msec\nrounds: 34"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 890.1160368874109,
            "unit": "iter/sec",
            "range": "stddev: 0.0013544708363588222",
            "extra": "mean: 1.123449031990071 msec\nrounds: 844"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 65.60712372643802,
            "unit": "iter/sec",
            "range": "stddev: 0.01084298835507494",
            "extra": "mean: 15.24224723171373 msec\nrounds: 82"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 5.701921951821846,
            "unit": "iter/sec",
            "range": "stddev: 0.04418978329875094",
            "extra": "mean: 175.37946124998882 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 278.3674885960359,
            "unit": "iter/sec",
            "range": "stddev: 0.00015394471208077077",
            "extra": "mean: 3.5923735384601247 msec\nrounds: 247"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 65.99911759650595,
            "unit": "iter/sec",
            "range": "stddev: 0.0108860097305735",
            "extra": "mean: 15.151717726191853 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 31.0285924850755,
            "unit": "iter/sec",
            "range": "stddev: 0.016038998365999133",
            "extra": "mean: 32.22833908695639 msec\nrounds: 46"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 22.207694606415032,
            "unit": "iter/sec",
            "range": "stddev: 0.018217562654034937",
            "extra": "mean: 45.02943766666959 msec\nrounds: 33"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 15656.340942553554,
            "unit": "iter/sec",
            "range": "stddev: 0.000003968063143256843",
            "extra": "mean: 63.87188447602238 usec\nrounds: 9946"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 962.2842741070199,
            "unit": "iter/sec",
            "range": "stddev: 0.000024310698744430188",
            "extra": "mean: 1.0391939543311974 msec\nrounds: 635"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 61.38813394466427,
            "unit": "iter/sec",
            "range": "stddev: 0.0019929038153745564",
            "extra": "mean: 16.28979308772291 msec\nrounds: 57"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1066.237505718477,
            "unit": "iter/sec",
            "range": "stddev: 0.00002309973607151777",
            "extra": "mean: 937.8773440596208 usec\nrounds: 808"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 963.2162002983326,
            "unit": "iter/sec",
            "range": "stddev: 0.00001866266279707085",
            "extra": "mean: 1.0381885185177269 msec\nrounds: 756"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 902.7725197723523,
            "unit": "iter/sec",
            "range": "stddev: 0.000016351060646745438",
            "extra": "mean: 1.1076987592092027 msec\nrounds: 706"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 883.5328935260998,
            "unit": "iter/sec",
            "range": "stddev: 0.000022137768457179978",
            "extra": "mean: 1.1318197741445601 msec\nrounds: 642"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 140.41543450870793,
            "unit": "iter/sec",
            "range": "stddev: 0.000590547194136484",
            "extra": "mean: 7.121724214284895 msec\nrounds: 126"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 136.6544678786618,
            "unit": "iter/sec",
            "range": "stddev: 0.0005688669199785769",
            "extra": "mean: 7.317726346773527 msec\nrounds: 124"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 96.25184911393329,
            "unit": "iter/sec",
            "range": "stddev: 0.0005145428759056552",
            "extra": "mean: 10.38941079268306 msec\nrounds: 82"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 60.06417993199138,
            "unit": "iter/sec",
            "range": "stddev: 0.012245503653576514",
            "extra": "mean: 16.648857957142937 msec\nrounds: 70"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 16.855931286882626,
            "unit": "iter/sec",
            "range": "stddev: 0.02108587386742683",
            "extra": "mean: 59.326297846159655 msec\nrounds: 13"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 5.988960919652514,
            "unit": "iter/sec",
            "range": "stddev: 0.029471426756852614",
            "extra": "mean: 166.97387299999633 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.0468316690597335,
            "unit": "iter/sec",
            "range": "stddev: 0.01707744237738225",
            "extra": "mean: 488.5599607999893 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 40.2348822887078,
            "unit": "iter/sec",
            "range": "stddev: 0.015107908970921161",
            "extra": "mean: 24.854055563638543 msec\nrounds: 55"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 13.459166327474769,
            "unit": "iter/sec",
            "range": "stddev: 0.021565973976309414",
            "extra": "mean: 74.29880689999777 msec\nrounds: 10"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 5.700781691755432,
            "unit": "iter/sec",
            "range": "stddev: 0.0215186399222139",
            "extra": "mean: 175.4145403333401 msec\nrounds: 6"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 2.902780808280902,
            "unit": "iter/sec",
            "range": "stddev: 0.03882460125683247",
            "extra": "mean: 344.4972480000047 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 39.72425166684675,
            "unit": "iter/sec",
            "range": "stddev: 0.015348223568155931",
            "extra": "mean: 25.173539035716683 msec\nrounds: 56"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 429604.3029575759,
            "unit": "iter/sec",
            "range": "stddev: 4.2314326154148623e-7",
            "extra": "mean: 2.3277234262217146 usec\nrounds: 80756"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1466066.4976098454,
            "unit": "iter/sec",
            "range": "stddev: 2.462351665192475e-7",
            "extra": "mean: 682.097300245465 nsec\nrounds: 103864"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 125.48706967077939,
            "unit": "iter/sec",
            "range": "stddev: 0.00012376996096889113",
            "extra": "mean: 7.968948534885244 msec\nrounds: 129"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3270299.2452606875,
            "unit": "iter/sec",
            "range": "stddev: 3.888187040582651e-8",
            "extra": "mean: 305.782414697737 nsec\nrounds: 192679"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4307550.861664087,
            "unit": "iter/sec",
            "range": "stddev: 3.280121632128463e-8",
            "extra": "mean: 232.1504799629183 nsec\nrounds: 195734"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4049001.700022243,
            "unit": "iter/sec",
            "range": "stddev: 3.364030000338988e-8",
            "extra": "mean: 246.97445792490197 nsec\nrounds: 193424"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 3898274.041985648,
            "unit": "iter/sec",
            "range": "stddev: 3.35345478062071e-8",
            "extra": "mean: 256.52378186594444 nsec\nrounds: 194970"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3406830.3283605324,
            "unit": "iter/sec",
            "range": "stddev: 3.654732981673861e-8",
            "extra": "mean: 293.52797281255556 nsec\nrounds: 188715"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 29252.615810210453,
            "unit": "iter/sec",
            "range": "stddev: 0.0000031835796988545573",
            "extra": "mean: 34.18497704574358 usec\nrounds: 5097"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 29.49678174723591,
            "unit": "iter/sec",
            "range": "stddev: 0.00033985444705070717",
            "extra": "mean: 33.90200356666735 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 6525732.531941178,
            "unit": "iter/sec",
            "range": "stddev: 1.3632067693772259e-8",
            "extra": "mean: 153.23950148207112 nsec\nrounds: 67440"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 32158.757115885517,
            "unit": "iter/sec",
            "range": "stddev: 0.000003690766847068176",
            "extra": "mean: 31.09572911653443 usec\nrounds: 10750"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 31910.919625744762,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034882770200853367",
            "extra": "mean: 31.337235395536215 usec\nrounds: 17991"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 31475.359425905095,
            "unit": "iter/sec",
            "range": "stddev: 0.000005146378852001731",
            "extra": "mean: 31.770884216717548 usec\nrounds: 12722"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 210968.9827867945,
            "unit": "iter/sec",
            "range": "stddev: 8.023046001933346e-7",
            "extra": "mean: 4.740033282573113 usec\nrounds: 69556"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 211251.6853011364,
            "unit": "iter/sec",
            "range": "stddev: 8.118528892299243e-7",
            "extra": "mean: 4.7336900464226535 usec\nrounds: 113046"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 210886.17521149456,
            "unit": "iter/sec",
            "range": "stddev: 7.947540119550011e-7",
            "extra": "mean: 4.74189452673754 usec\nrounds: 115527"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 184427.94408169418,
            "unit": "iter/sec",
            "range": "stddev: 8.582555385471307e-7",
            "extra": "mean: 5.4221718133833345 usec\nrounds: 22117"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 217.96707236829306,
            "unit": "iter/sec",
            "range": "stddev: 0.00003277209551465416",
            "extra": "mean: 4.587848931192355 msec\nrounds: 218"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 31954.49447849023,
            "unit": "iter/sec",
            "range": "stddev: 0.0000037109925442859297",
            "extra": "mean: 31.294502270193558 usec\nrounds: 9690"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 31979.726841897456,
            "unit": "iter/sec",
            "range": "stddev: 0.000003634978000016675",
            "extra": "mean: 31.269810556664122 usec\nrounds: 11064"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 31824.722476478644,
            "unit": "iter/sec",
            "range": "stddev: 0.000004141353746059882",
            "extra": "mean: 31.422112187752482 usec\nrounds: 11454"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 31548.30799703704,
            "unit": "iter/sec",
            "range": "stddev: 0.0000037393704013431324",
            "extra": "mean: 31.697420986695015 usec\nrounds: 14352"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.2923104970522092,
            "unit": "iter/sec",
            "range": "stddev: 0.001154078220277561",
            "extra": "mean: 303.73805900001116 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 26055.085043246854,
            "unit": "iter/sec",
            "range": "stddev: 0.000003976817388739053",
            "extra": "mean: 38.380223988529536 usec\nrounds: 10255"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 26043.885736690478,
            "unit": "iter/sec",
            "range": "stddev: 0.000004065661411933422",
            "extra": "mean: 38.39672812690949 usec\nrounds: 13407"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 25826.79375437208,
            "unit": "iter/sec",
            "range": "stddev: 0.000004345541462894376",
            "extra": "mean: 38.719479061574006 usec\nrounds: 12871"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 172918.76004356096,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010985987783201467",
            "extra": "mean: 5.783062518769416 usec\nrounds: 29975"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 19230.422196748445,
            "unit": "iter/sec",
            "range": "stddev: 0.0000035098351988437065",
            "extra": "mean: 52.0009383969263 usec\nrounds: 12613"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1940.6802276241324,
            "unit": "iter/sec",
            "range": "stddev: 0.000012249091472059633",
            "extra": "mean: 515.2832423218146 usec\nrounds: 1791"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 197639.28185800457,
            "unit": "iter/sec",
            "range": "stddev: 9.777335167013939e-7",
            "extra": "mean: 5.059722898196207 usec\nrounds: 23670"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 3135.813760443083,
            "unit": "iter/sec",
            "range": "stddev: 0.000022552408228167714",
            "extra": "mean: 318.89648952197416 usec\nrounds: 2386"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 392.98490178829593,
            "unit": "iter/sec",
            "range": "stddev: 0.0016335318830463747",
            "extra": "mean: 2.5446270211640547 msec\nrounds: 945"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 348.9952694397497,
            "unit": "iter/sec",
            "range": "stddev: 0.0019890890684015716",
            "extra": "mean: 2.865368351855667 msec\nrounds: 324"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 46295.16575935361,
            "unit": "iter/sec",
            "range": "stddev: 0.0000021831629435729",
            "extra": "mean: 21.60052747619674 usec\nrounds: 14649"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 29.74087280047765,
            "unit": "iter/sec",
            "range": "stddev: 0.0001711460231808996",
            "extra": "mean: 33.62376103447575 msec\nrounds: 29"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 22466.905039219808,
            "unit": "iter/sec",
            "range": "stddev: 0.000004311328719057389",
            "extra": "mean: 44.50991350407766 usec\nrounds: 8960"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 8424.821416270013,
            "unit": "iter/sec",
            "range": "stddev: 0.000009795802017995836",
            "extra": "mean: 118.69687802150916 usec\nrounds: 5378"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 11614.174520967026,
            "unit": "iter/sec",
            "range": "stddev: 0.000006448471910569225",
            "extra": "mean: 86.1016853324103 usec\nrounds: 6804"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3352.624354927834,
            "unit": "iter/sec",
            "range": "stddev: 0.00012472547435756623",
            "extra": "mean: 298.27379811584206 usec\nrounds: 2016"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 2065799.4687878594,
            "unit": "iter/sec",
            "range": "stddev: 4.2060070089279704e-8",
            "extra": "mean: 484.07409097978217 nsec\nrounds: 53519"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1897019.4752484486,
            "unit": "iter/sec",
            "range": "stddev: 6.841677989206776e-8",
            "extra": "mean: 527.1427167973761 nsec\nrounds: 191976"
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
          "id": "a4bdc85458cfbbdd487ad7d64d67b3e324885f0c",
          "message": "Bump version to 0.11.1",
          "timestamp": "2026-03-12T20:50:59+09:00",
          "tree_id": "f42dd88883cf80febc62f9ce1370d587315ccf88",
          "url": "https://github.com/cognica-io/uqa/commit/a4bdc85458cfbbdd487ad7d64d67b3e324885f0c"
        },
        "date": 1773316614353,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 18013.40738377367,
            "unit": "iter/sec",
            "range": "stddev: 0.000003861137456907884",
            "extra": "mean: 55.514205541189945 usec\nrounds: 3104"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 5870.988467109094,
            "unit": "iter/sec",
            "range": "stddev: 0.000007681691171186802",
            "extra": "mean: 170.32906904898167 usec\nrounds: 3722"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 9082.438940608537,
            "unit": "iter/sec",
            "range": "stddev: 0.000005380623284535127",
            "extra": "mean: 110.10258439821655 usec\nrounds: 6025"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 3844.7758720940806,
            "unit": "iter/sec",
            "range": "stddev: 0.000012482890772985374",
            "extra": "mean: 260.09318443192996 usec\nrounds: 2852"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 8639.665838779767,
            "unit": "iter/sec",
            "range": "stddev: 0.000006168750670888125",
            "extra": "mean: 115.7452173105385 usec\nrounds: 5384"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 4722.053202673243,
            "unit": "iter/sec",
            "range": "stddev: 0.00007424932878371096",
            "extra": "mean: 211.7722857154344 usec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 1546.6985384911268,
            "unit": "iter/sec",
            "range": "stddev: 0.000025846599613430278",
            "extra": "mean: 646.538401061363 usec\nrounds: 1319"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4141.928888503132,
            "unit": "iter/sec",
            "range": "stddev: 0.00002142287817541657",
            "extra": "mean: 241.43340625082388 usec\nrounds: 64"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 5163.535153885115,
            "unit": "iter/sec",
            "range": "stddev: 0.000014750723269813926",
            "extra": "mean: 193.66576777299295 usec\nrounds: 211"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 3746.232444463301,
            "unit": "iter/sec",
            "range": "stddev: 0.00003755251076698892",
            "extra": "mean: 266.934851167054 usec\nrounds: 3299"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 9464.443267593575,
            "unit": "iter/sec",
            "range": "stddev: 0.000006658655331985562",
            "extra": "mean: 105.65861844446975 usec\nrounds: 5606"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 7269.5812427617575,
            "unit": "iter/sec",
            "range": "stddev: 0.0000075257952905966615",
            "extra": "mean: 137.55950536981607 usec\nrounds: 5028"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 6176.868375372443,
            "unit": "iter/sec",
            "range": "stddev: 0.000008647898901992184",
            "extra": "mean: 161.89433532161087 usec\nrounds: 3856"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 5511.298317286521,
            "unit": "iter/sec",
            "range": "stddev: 0.00000973444674364607",
            "extra": "mean: 181.44544940770842 usec\nrounds: 4052"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 3334.274633931019,
            "unit": "iter/sec",
            "range": "stddev: 0.000014242428243286613",
            "extra": "mean: 299.91530686271847 usec\nrounds: 1020"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1344.2490554365215,
            "unit": "iter/sec",
            "range": "stddev: 0.000046173065153015266",
            "extra": "mean: 743.90976579505 usec\nrounds: 918"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 9105.781577029928,
            "unit": "iter/sec",
            "range": "stddev: 0.000007247139551406455",
            "extra": "mean: 109.82033684209833 usec\nrounds: 5795"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 7957.28322541554,
            "unit": "iter/sec",
            "range": "stddev: 0.000012469989206176699",
            "extra": "mean: 125.67103264667053 usec\nrounds: 6310"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 3486.8837572195275,
            "unit": "iter/sec",
            "range": "stddev: 0.0000161826187931183",
            "extra": "mean: 286.7890270014074 usec\nrounds: 2111"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 5110.044573012838,
            "unit": "iter/sec",
            "range": "stddev: 0.00001666757521896342",
            "extra": "mean: 195.69300927064293 usec\nrounds: 4099"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 3418.204841724645,
            "unit": "iter/sec",
            "range": "stddev: 0.0002641293425245805",
            "extra": "mean: 292.5512209781591 usec\nrounds: 2679"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1789.323162850809,
            "unit": "iter/sec",
            "range": "stddev: 0.000016447383439147526",
            "extra": "mean: 558.870538738663 usec\nrounds: 1110"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1474.178035973472,
            "unit": "iter/sec",
            "range": "stddev: 0.0000172823667142609",
            "extra": "mean: 678.3441182798866 usec\nrounds: 1116"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1645.7524927586348,
            "unit": "iter/sec",
            "range": "stddev: 0.00033660903333151694",
            "extra": "mean: 607.6247822197037 usec\nrounds: 6929"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 1198.7185457104301,
            "unit": "iter/sec",
            "range": "stddev: 0.000026437050391152982",
            "extra": "mean: 834.2241834653038 usec\nrounds: 883"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 979.9624262497979,
            "unit": "iter/sec",
            "range": "stddev: 0.000045396713096951406",
            "extra": "mean: 1.0204472877872304 msec\nrounds: 827"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 94.16234663533115,
            "unit": "iter/sec",
            "range": "stddev: 0.0033043338784106394",
            "extra": "mean: 10.619956232322536 msec\nrounds: 99"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 100.85265931242047,
            "unit": "iter/sec",
            "range": "stddev: 0.0024520374647291543",
            "extra": "mean: 9.915454949999969 msec\nrounds: 100"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 158.72638275671218,
            "unit": "iter/sec",
            "range": "stddev: 0.0026704988972953056",
            "extra": "mean: 6.300149871951342 msec\nrounds: 164"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 169.92618511851467,
            "unit": "iter/sec",
            "range": "stddev: 0.0024620930341749782",
            "extra": "mean: 5.884908198830875 msec\nrounds: 171"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 84.32471143614924,
            "unit": "iter/sec",
            "range": "stddev: 0.0029669941130968593",
            "extra": "mean: 11.858919917647166 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 60.03040421880653,
            "unit": "iter/sec",
            "range": "stddev: 0.003605196221823273",
            "extra": "mean: 16.65822532787005 msec\nrounds: 61"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 237.65668304639598,
            "unit": "iter/sec",
            "range": "stddev: 0.0012646070098220592",
            "extra": "mean: 4.207750386740765 msec\nrounds: 181"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 81.83984576966732,
            "unit": "iter/sec",
            "range": "stddev: 0.001886603181257424",
            "extra": "mean: 12.218986858973707 msec\nrounds: 78"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10831695102128536,
            "unit": "iter/sec",
            "range": "stddev: 0.031427850935208515",
            "extra": "mean: 9.232165331200008 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 13.220450816220831,
            "unit": "iter/sec",
            "range": "stddev: 0.00022386662850176756",
            "extra": "mean: 75.6403857857139 msec\nrounds: 14"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 18.994902980096033,
            "unit": "iter/sec",
            "range": "stddev: 0.007180006646946516",
            "extra": "mean: 52.64570190476142 msec\nrounds: 21"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 69.58773971682609,
            "unit": "iter/sec",
            "range": "stddev: 0.004103757651307335",
            "extra": "mean: 14.370347478870666 msec\nrounds: 71"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 166.59862233947788,
            "unit": "iter/sec",
            "range": "stddev: 0.0017608357511368006",
            "extra": "mean: 6.002450596273844 msec\nrounds: 161"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 144.1557991284952,
            "unit": "iter/sec",
            "range": "stddev: 0.0014734506698809253",
            "extra": "mean: 6.936939103702908 msec\nrounds: 135"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 339.04384572580705,
            "unit": "iter/sec",
            "range": "stddev: 0.0002914325426241276",
            "extra": "mean: 2.94947102743969 msec\nrounds: 328"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 1904.964613142893,
            "unit": "iter/sec",
            "range": "stddev: 0.000014691395809454338",
            "extra": "mean: 524.9441344478083 usec\nrounds: 1495"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 478.4478181672749,
            "unit": "iter/sec",
            "range": "stddev: 0.0010667225329342564",
            "extra": "mean: 2.090092089520994 msec\nrounds: 458"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 227.59806942124987,
            "unit": "iter/sec",
            "range": "stddev: 0.002614660038116063",
            "extra": "mean: 4.393710379630462 msec\nrounds: 216"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 211.11358756732292,
            "unit": "iter/sec",
            "range": "stddev: 0.0025598431953670273",
            "extra": "mean: 4.736786539999969 msec\nrounds: 200"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1597.3318333405182,
            "unit": "iter/sec",
            "range": "stddev: 0.000014533720970595868",
            "extra": "mean: 626.0439935693817 usec\nrounds: 1244"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 124.69870911881243,
            "unit": "iter/sec",
            "range": "stddev: 0.003469517886769449",
            "extra": "mean: 8.019329206104324 msec\nrounds: 131"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 223.36485987590012,
            "unit": "iter/sec",
            "range": "stddev: 0.002822817163740125",
            "extra": "mean: 4.476979953586221 msec\nrounds: 237"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 72.72996298536728,
            "unit": "iter/sec",
            "range": "stddev: 0.0035744386399320463",
            "extra": "mean: 13.749491391892947 msec\nrounds: 74"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 89.82138182412302,
            "unit": "iter/sec",
            "range": "stddev: 0.0034813028323206524",
            "extra": "mean: 11.133206589474147 msec\nrounds: 95"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 83.68749620201667,
            "unit": "iter/sec",
            "range": "stddev: 0.0036731375695601234",
            "extra": "mean: 11.949216375001338 msec\nrounds: 88"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 95.49115143332742,
            "unit": "iter/sec",
            "range": "stddev: 0.0018015003988665619",
            "extra": "mean: 10.4721744893631 msec\nrounds: 94"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 100.77596582828332,
            "unit": "iter/sec",
            "range": "stddev: 0.003371850070712849",
            "extra": "mean: 9.92300090384591 msec\nrounds: 104"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 97.1163779683745,
            "unit": "iter/sec",
            "range": "stddev: 0.0029082734657299597",
            "extra": "mean: 10.296924380001542 msec\nrounds: 100"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 84.58309739529464,
            "unit": "iter/sec",
            "range": "stddev: 0.004276479231681936",
            "extra": "mean: 11.822693076922363 msec\nrounds: 91"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 167.29654955319316,
            "unit": "iter/sec",
            "range": "stddev: 0.00295261482899377",
            "extra": "mean: 5.977409591953614 msec\nrounds: 174"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 152.94063472908422,
            "unit": "iter/sec",
            "range": "stddev: 0.003500230651815325",
            "extra": "mean: 6.5384846987942655 msec\nrounds: 166"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 172.0250622495844,
            "unit": "iter/sec",
            "range": "stddev: 0.00003815221909805194",
            "extra": "mean: 5.813106456250772 msec\nrounds: 160"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 144.50577736727126,
            "unit": "iter/sec",
            "range": "stddev: 0.0013817337985867228",
            "extra": "mean: 6.920138545453668 msec\nrounds: 143"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 37.835702585618044,
            "unit": "iter/sec",
            "range": "stddev: 0.0027517389826465636",
            "extra": "mean: 26.430062921049494 msec\nrounds: 38"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 222.2406597547723,
            "unit": "iter/sec",
            "range": "stddev: 0.0029635606874625167",
            "extra": "mean: 4.499626670940561 msec\nrounds: 234"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 223.6493154249944,
            "unit": "iter/sec",
            "range": "stddev: 0.0026929523954739823",
            "extra": "mean: 4.471285763158848 msec\nrounds: 228"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 53.130970584235314,
            "unit": "iter/sec",
            "range": "stddev: 0.005386887197184422",
            "extra": "mean: 18.821414120688278 msec\nrounds: 58"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 94.28057482050284,
            "unit": "iter/sec",
            "range": "stddev: 0.0030180703205983463",
            "extra": "mean: 10.606638768419279 msec\nrounds: 95"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 637799.0479750781,
            "unit": "iter/sec",
            "range": "stddev: 3.3920528110934545e-7",
            "extra": "mean: 1.5678919609159951 usec\nrounds: 66587"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 260787.6255669128,
            "unit": "iter/sec",
            "range": "stddev: 5.317648705105652e-7",
            "extra": "mean: 3.8345377692908222 usec\nrounds: 81018"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 77421.35211254329,
            "unit": "iter/sec",
            "range": "stddev: 0.000001650657169774282",
            "extra": "mean: 12.916333449541844 usec\nrounds: 34467"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 776074.7001043612,
            "unit": "iter/sec",
            "range": "stddev: 3.168588431605363e-7",
            "extra": "mean: 1.2885357554698367 usec\nrounds: 141363"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2192856.4472053717,
            "unit": "iter/sec",
            "range": "stddev: 4.344866173813487e-8",
            "extra": "mean: 456.02620329954743 nsec\nrounds: 105065"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1682947.30142239,
            "unit": "iter/sec",
            "range": "stddev: 7.566661725746963e-8",
            "extra": "mean: 594.1956703901674 nsec\nrounds: 180473"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2483943.7097075316,
            "unit": "iter/sec",
            "range": "stddev: 4.171623447339505e-8",
            "extra": "mean: 402.5856125852963 nsec\nrounds: 117151"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 177122.93645361444,
            "unit": "iter/sec",
            "range": "stddev: 6.974857753038385e-7",
            "extra": "mean: 5.645796191177552 usec\nrounds: 95148"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1629.753038631445,
            "unit": "iter/sec",
            "range": "stddev: 0.00001911793544922065",
            "extra": "mean: 613.5898975465212 usec\nrounds: 693"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1643.0226889654366,
            "unit": "iter/sec",
            "range": "stddev: 0.00000999139015247388",
            "extra": "mean: 608.6343217997013 usec\nrounds: 1445"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 448996.7186994048,
            "unit": "iter/sec",
            "range": "stddev: 4.878007771938665e-7",
            "extra": "mean: 2.2271877685357473 usec\nrounds: 70294"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 197728.46922418472,
            "unit": "iter/sec",
            "range": "stddev: 7.47380868174999e-7",
            "extra": "mean: 5.057440660536339 usec\nrounds: 68976"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 117895.89026096462,
            "unit": "iter/sec",
            "range": "stddev: 9.666772959364958e-7",
            "extra": "mean: 8.48205987321935 usec\nrounds: 50490"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 339356.64152301784,
            "unit": "iter/sec",
            "range": "stddev: 5.377898522523526e-7",
            "extra": "mean: 2.9467524062945802 usec\nrounds: 99118"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 103325.1638337387,
            "unit": "iter/sec",
            "range": "stddev: 9.928021339402297e-7",
            "extra": "mean: 9.678184508946027 usec\nrounds: 49293"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 16163.835732563324,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034287221257397914",
            "extra": "mean: 61.86650350482225 usec\nrounds: 6705"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 10402.207915144036,
            "unit": "iter/sec",
            "range": "stddev: 0.000005034626839193266",
            "extra": "mean: 96.13343707004277 usec\nrounds: 7850"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 12635.239041663941,
            "unit": "iter/sec",
            "range": "stddev: 0.000003834731391910093",
            "extra": "mean: 79.14373417887546 usec\nrounds: 8201"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 92467.52145015127,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012755869446060677",
            "extra": "mean: 10.814608030118926 usec\nrounds: 28941"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 26660.3166969736,
            "unit": "iter/sec",
            "range": "stddev: 0.000002883990200971001",
            "extra": "mean: 37.50893177174887 usec\nrounds: 13235"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 6106.012068326707,
            "unit": "iter/sec",
            "range": "stddev: 0.000005628503527981577",
            "extra": "mean: 163.77301400814954 usec\nrounds: 4069"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2130.0339103553574,
            "unit": "iter/sec",
            "range": "stddev: 0.000011827344533852811",
            "extra": "mean: 469.47609384921395 usec\nrounds: 1577"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 91346.641147111,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013416083185700607",
            "extra": "mean: 10.94731002084171 usec\nrounds: 35446"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 18384.513326027158,
            "unit": "iter/sec",
            "range": "stddev: 0.0000027273159963650137",
            "extra": "mean: 54.39360739477878 usec\nrounds: 11197"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1355.658347705329,
            "unit": "iter/sec",
            "range": "stddev: 0.000009741280492363435",
            "extra": "mean: 737.6489819080608 usec\nrounds: 608"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 185.10450399092466,
            "unit": "iter/sec",
            "range": "stddev: 0.00005429164458030307",
            "extra": "mean: 5.402353689076244 msec\nrounds: 119"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.38023993487429786,
            "unit": "iter/sec",
            "range": "stddev: 0.02505961747467837",
            "extra": "mean: 2.6299183970000057 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 72415.18408662989,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013532307744906422",
            "extra": "mean: 13.809258550025994 usec\nrounds: 26316"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 6594.138307029513,
            "unit": "iter/sec",
            "range": "stddev: 0.000004754570000772549",
            "extra": "mean: 151.64983708849047 usec\nrounds: 5015"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 158.56653316950639,
            "unit": "iter/sec",
            "range": "stddev: 0.00004010422698838217",
            "extra": "mean: 6.306500999999842 msec\nrounds: 152"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 72619.75284583266,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012572108188161013",
            "extra": "mean: 13.770358074929552 usec\nrounds: 30731"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 15059.868914308785,
            "unit": "iter/sec",
            "range": "stddev: 0.0000030244004513114195",
            "extra": "mean: 66.40164039209354 usec\nrounds: 9185"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 2751.692606080465,
            "unit": "iter/sec",
            "range": "stddev: 0.000010686938671293302",
            "extra": "mean: 363.41268562857704 usec\nrounds: 2004"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 791.7904237038015,
            "unit": "iter/sec",
            "range": "stddev: 0.00001562503843804235",
            "extra": "mean: 1.2629604628485467 msec\nrounds: 646"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6207.042851417397,
            "unit": "iter/sec",
            "range": "stddev: 0.000006048403153247657",
            "extra": "mean: 161.10731373018427 usec\nrounds: 4268"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1351.5399310084345,
            "unit": "iter/sec",
            "range": "stddev: 0.000010900994393307546",
            "extra": "mean: 739.8967481884629 usec\nrounds: 1104"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 161.58624411191724,
            "unit": "iter/sec",
            "range": "stddev: 0.000048664688644039735",
            "extra": "mean: 6.188645608393397 msec\nrounds: 143"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 2742.744876985792,
            "unit": "iter/sec",
            "range": "stddev: 0.000010322529789774432",
            "extra": "mean: 364.5982564368054 usec\nrounds: 1942"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 54.32027287204632,
            "unit": "iter/sec",
            "range": "stddev: 0.00020498583471383335",
            "extra": "mean: 18.409333148151557 msec\nrounds: 54"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1254.52574752646,
            "unit": "iter/sec",
            "range": "stddev: 0.000014303157238744135",
            "extra": "mean: 797.1139707349118 usec\nrounds: 1196"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 406.2596731830626,
            "unit": "iter/sec",
            "range": "stddev: 0.00003447437249387012",
            "extra": "mean: 2.4614798514579497 msec\nrounds: 377"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1475.777047646156,
            "unit": "iter/sec",
            "range": "stddev: 0.000011055283932281773",
            "extra": "mean: 677.609129099132 usec\nrounds: 1433"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 480.0125985766209,
            "unit": "iter/sec",
            "range": "stddev: 0.000023103873903607084",
            "extra": "mean: 2.083278653446379 msec\nrounds: 479"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 344.1618628726333,
            "unit": "iter/sec",
            "range": "stddev: 0.00032355902026289825",
            "extra": "mean: 2.905609563050505 msec\nrounds: 341"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1635.0058848191895,
            "unit": "iter/sec",
            "range": "stddev: 0.000015855198115867136",
            "extra": "mean: 611.6185937218122 usec\nrounds: 1147"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1262.648009940754,
            "unit": "iter/sec",
            "range": "stddev: 0.000017150938800606515",
            "extra": "mean: 791.9863589274751 usec\nrounds: 1081"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 852.9818718266316,
            "unit": "iter/sec",
            "range": "stddev: 0.001340032608409656",
            "extra": "mean: 1.1723578578036298 msec\nrounds: 865"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 68.17152482290838,
            "unit": "iter/sec",
            "range": "stddev: 0.009775110333620322",
            "extra": "mean: 14.668881216867835 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 5.889146058164115,
            "unit": "iter/sec",
            "range": "stddev: 0.044412288361459995",
            "extra": "mean: 169.8039053749909 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 266.37998099529904,
            "unit": "iter/sec",
            "range": "stddev: 0.000033577297586372",
            "extra": "mean: 3.754035856086526 msec\nrounds: 271"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 70.42196749023663,
            "unit": "iter/sec",
            "range": "stddev: 0.008678181590290945",
            "extra": "mean: 14.200114476191553 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 35.840549470985245,
            "unit": "iter/sec",
            "range": "stddev: 0.012537939757908219",
            "extra": "mean: 27.901357952381595 msec\nrounds: 21"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 25.0079598252082,
            "unit": "iter/sec",
            "range": "stddev: 0.015149813293631792",
            "extra": "mean: 39.98726833334053 msec\nrounds: 18"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 909.0041587789418,
            "unit": "iter/sec",
            "range": "stddev: 0.0010259429952516725",
            "extra": "mean: 1.100104977895032 msec\nrounds: 769"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 70.40883028122025,
            "unit": "iter/sec",
            "range": "stddev: 0.009412959547456379",
            "extra": "mean: 14.202763999996806 msec\nrounds: 90"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 6.216206340176529,
            "unit": "iter/sec",
            "range": "stddev: 0.04391444384127745",
            "extra": "mean: 160.86982079999643 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 291.80972395205026,
            "unit": "iter/sec",
            "range": "stddev: 0.000044289403669805186",
            "extra": "mean: 3.4268906000004256 msec\nrounds: 280"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 72.84453757594885,
            "unit": "iter/sec",
            "range": "stddev: 0.009220430319184974",
            "extra": "mean: 13.727865304346047 msec\nrounds: 23"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 34.6114283960005,
            "unit": "iter/sec",
            "range": "stddev: 0.013053013554720824",
            "extra": "mean: 28.892190999997975 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 24.724604681695993,
            "unit": "iter/sec",
            "range": "stddev: 0.014777506015877458",
            "extra": "mean: 40.445540499999 msec\nrounds: 36"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 15844.29650124159,
            "unit": "iter/sec",
            "range": "stddev: 0.000013259199525350688",
            "extra": "mean: 63.11419379974606 usec\nrounds: 9613"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 984.5216198852436,
            "unit": "iter/sec",
            "range": "stddev: 0.000013709936624067176",
            "extra": "mean: 1.0157217269810292 msec\nrounds: 934"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 67.7338720899535,
            "unit": "iter/sec",
            "range": "stddev: 0.0005905729405669411",
            "extra": "mean: 14.7636620961512 msec\nrounds: 52"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1097.3972538144926,
            "unit": "iter/sec",
            "range": "stddev: 0.00002458531377376699",
            "extra": "mean: 911.2470406901921 usec\nrounds: 811"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 970.1675359253652,
            "unit": "iter/sec",
            "range": "stddev: 0.000038941417309019004",
            "extra": "mean: 1.0307498065745726 msec\nrounds: 791"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 911.4925400562246,
            "unit": "iter/sec",
            "range": "stddev: 0.000014623816241002838",
            "extra": "mean: 1.0971016832878477 msec\nrounds: 742"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 908.1416013764223,
            "unit": "iter/sec",
            "range": "stddev: 0.000013901081360750334",
            "extra": "mean: 1.1011498630657959 msec\nrounds: 796"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 182.48171283475875,
            "unit": "iter/sec",
            "range": "stddev: 0.0001437856839465548",
            "extra": "mean: 5.480001170887311 msec\nrounds: 158"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 169.7195931292471,
            "unit": "iter/sec",
            "range": "stddev: 0.0002035264025633408",
            "extra": "mean: 5.892071631579195 msec\nrounds: 133"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 114.5017022225037,
            "unit": "iter/sec",
            "range": "stddev: 0.00020636629122531538",
            "extra": "mean: 8.733494617021195 msec\nrounds: 94"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 64.24875545301276,
            "unit": "iter/sec",
            "range": "stddev: 0.010443680692451189",
            "extra": "mean: 15.564503825001452 msec\nrounds: 80"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 18.239208783348463,
            "unit": "iter/sec",
            "range": "stddev: 0.018989312810031748",
            "extra": "mean: 54.82693969230468 msec\nrounds: 13"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 6.61230600268398,
            "unit": "iter/sec",
            "range": "stddev: 0.025308622606773606",
            "extra": "mean: 151.23317033332899 msec\nrounds: 9"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.4907263396423507,
            "unit": "iter/sec",
            "range": "stddev: 0.03761403665663452",
            "extra": "mean: 401.48931020000873 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 44.176604271785415,
            "unit": "iter/sec",
            "range": "stddev: 0.012674624215491204",
            "extra": "mean: 22.636416186444574 msec\nrounds: 59"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 14.358364421009792,
            "unit": "iter/sec",
            "range": "stddev: 0.021423969654299633",
            "extra": "mean: 69.64581554545 msec\nrounds: 11"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 6.40278438550402,
            "unit": "iter/sec",
            "range": "stddev: 0.00272231934534862",
            "extra": "mean: 156.18205140001464 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 3.006516870046296,
            "unit": "iter/sec",
            "range": "stddev: 0.040376090688865204",
            "extra": "mean: 332.6108062000003 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 44.57704696053466,
            "unit": "iter/sec",
            "range": "stddev: 0.013037841091838183",
            "extra": "mean: 22.433069666667883 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 446651.18921582185,
            "unit": "iter/sec",
            "range": "stddev: 3.883401737584959e-7",
            "extra": "mean: 2.2388835497240778 usec\nrounds: 73774"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1469203.0026511955,
            "unit": "iter/sec",
            "range": "stddev: 2.275555002065562e-7",
            "extra": "mean: 680.6411354969241 nsec\nrounds: 97371"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 126.3617610877715,
            "unit": "iter/sec",
            "range": "stddev: 0.00006782815066054924",
            "extra": "mean: 7.913786507813825 msec\nrounds: 128"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3261509.061831788,
            "unit": "iter/sec",
            "range": "stddev: 4.953377827630199e-8",
            "extra": "mean: 306.60653735493895 nsec\nrounds: 193424"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4317353.122677181,
            "unit": "iter/sec",
            "range": "stddev: 3.606006741789483e-8",
            "extra": "mean: 231.6233978516685 nsec\nrounds: 196079"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4071470.989203265,
            "unit": "iter/sec",
            "range": "stddev: 3.047610342076445e-8",
            "extra": "mean: 245.61147620891862 nsec\nrounds: 193837"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 3927656.7397826924,
            "unit": "iter/sec",
            "range": "stddev: 3.365603572721969e-8",
            "extra": "mean: 254.6047341334945 nsec\nrounds: 193837"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3414654.4829426454,
            "unit": "iter/sec",
            "range": "stddev: 4.2092462156913216e-8",
            "extra": "mean: 292.8553986927048 nsec\nrounds: 197629"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 30432.48724954071,
            "unit": "iter/sec",
            "range": "stddev: 0.000002938061567851123",
            "extra": "mean: 32.85962109505499 usec\nrounds: 4513"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 30.69530188868027,
            "unit": "iter/sec",
            "range": "stddev: 0.00016100162914168105",
            "extra": "mean: 32.578275451618126 msec\nrounds: 31"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 6515123.165559671,
            "unit": "iter/sec",
            "range": "stddev: 1.1941989898874702e-8",
            "extra": "mean: 153.48903997490225 nsec\nrounds: 65665"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 33378.30530469901,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034093710517485667",
            "extra": "mean: 29.959579759108372 usec\nrounds: 11541"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 33253.67029176173,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034931586096776267",
            "extra": "mean: 30.071868495302315 usec\nrounds: 19140"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 32833.1677869661,
            "unit": "iter/sec",
            "range": "stddev: 0.0000033302324229144284",
            "extra": "mean: 30.457006356754086 usec\nrounds: 13844"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 218115.2140480372,
            "unit": "iter/sec",
            "range": "stddev: 9.283789766069432e-7",
            "extra": "mean: 4.584732909918711 usec\nrounds: 76023"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 220799.60657164312,
            "unit": "iter/sec",
            "range": "stddev: 8.375322832032518e-7",
            "extra": "mean: 4.52899357714901 usec\nrounds: 112411"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 217438.8933696366,
            "unit": "iter/sec",
            "range": "stddev: 7.753356327060177e-7",
            "extra": "mean: 4.5989932366885435 usec\nrounds: 117842"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 188361.30976264898,
            "unit": "iter/sec",
            "range": "stddev: 9.092192896523528e-7",
            "extra": "mean: 5.3089458831013845 usec\nrounds: 23246"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 227.99372824895653,
            "unit": "iter/sec",
            "range": "stddev: 0.000034147411492515894",
            "extra": "mean: 4.386085563318897 msec\nrounds: 229"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 33209.7175341513,
            "unit": "iter/sec",
            "range": "stddev: 0.000004156207169862254",
            "extra": "mean: 30.11166833839064 usec\nrounds: 9570"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 33264.49312034935,
            "unit": "iter/sec",
            "range": "stddev: 0.000003380075457103951",
            "extra": "mean: 30.06208440880334 usec\nrounds: 15887"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 33379.87929238027,
            "unit": "iter/sec",
            "range": "stddev: 0.000003452807105179825",
            "extra": "mean: 29.958167051498986 usec\nrounds: 15582"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 32791.76410004856,
            "unit": "iter/sec",
            "range": "stddev: 0.000003622650928337619",
            "extra": "mean: 30.495462121189117 usec\nrounds: 15444"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.440763282906634,
            "unit": "iter/sec",
            "range": "stddev: 0.001218205312170047",
            "extra": "mean: 290.6331873999875 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 27029.46538849243,
            "unit": "iter/sec",
            "range": "stddev: 0.00000394676777101728",
            "extra": "mean: 36.996662184289505 usec\nrounds: 10485"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 26950.10662952828,
            "unit": "iter/sec",
            "range": "stddev: 0.000004004981803173452",
            "extra": "mean: 37.1056045805895 usec\nrounds: 13492"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 26961.08699178032,
            "unit": "iter/sec",
            "range": "stddev: 0.000003825959601073425",
            "extra": "mean: 37.09049269062749 usec\nrounds: 13339"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 167663.63001436152,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011013031566877903",
            "extra": "mean: 5.964322733047968 usec\nrounds: 28584"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 19366.302292270037,
            "unit": "iter/sec",
            "range": "stddev: 0.0000035989797248475267",
            "extra": "mean: 51.63608338382413 usec\nrounds: 9870"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1900.969010225656,
            "unit": "iter/sec",
            "range": "stddev: 0.000013182942401133215",
            "extra": "mean: 526.0475024163042 usec\nrounds: 1863"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 197180.90381515116,
            "unit": "iter/sec",
            "range": "stddev: 9.156767379582977e-7",
            "extra": "mean: 5.071485020362105 usec\nrounds: 18692"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 3262.820983993965,
            "unit": "iter/sec",
            "range": "stddev: 0.00000878342315592727",
            "extra": "mean: 306.48325633112626 usec\nrounds: 2251"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 413.64265466494,
            "unit": "iter/sec",
            "range": "stddev: 0.0009427519941790303",
            "extra": "mean: 2.417545648937059 msec\nrounds: 940"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 373.8514376924638,
            "unit": "iter/sec",
            "range": "stddev: 0.0000320234394761464",
            "extra": "mean: 2.6748593135613836 msec\nrounds: 354"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 48052.66919064335,
            "unit": "iter/sec",
            "range": "stddev: 0.0000020491580915571295",
            "extra": "mean: 20.81049849765092 usec\nrounds: 15643"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 29.166371114108117,
            "unit": "iter/sec",
            "range": "stddev: 0.0007745421568374235",
            "extra": "mean: 34.28606171428328 msec\nrounds: 28"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 21948.04239202068,
            "unit": "iter/sec",
            "range": "stddev: 0.000004201425340037641",
            "extra": "mean: 45.56215001496238 usec\nrounds: 10139"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 8469.490036873376,
            "unit": "iter/sec",
            "range": "stddev: 0.00000653601249111169",
            "extra": "mean: 118.07086325697635 usec\nrounds: 6121"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 12093.553236956335,
            "unit": "iter/sec",
            "range": "stddev: 0.000004020200888513582",
            "extra": "mean: 82.6886838306652 usec\nrounds: 9419"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3667.8286553565617,
            "unit": "iter/sec",
            "range": "stddev: 0.00009987132601578245",
            "extra": "mean: 272.6408711976178 usec\nrounds: 2104"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 2076768.651066661,
            "unit": "iter/sec",
            "range": "stddev: 3.6578159898736625e-8",
            "extra": "mean: 481.5172838276349 nsec\nrounds: 51081"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1903631.255354358,
            "unit": "iter/sec",
            "range": "stddev: 6.944916170557841e-8",
            "extra": "mean: 525.3118203366815 nsec\nrounds: 186602"
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
          "id": "9e024d1a8e76696f818d3fd83f848ace2a0afacb",
          "message": "Bump version to 0.11.2",
          "timestamp": "2026-03-12T22:33:00+09:00",
          "tree_id": "2b54b70cd9ea25764de9f70e5c43decf4cff9b15",
          "url": "https://github.com/cognica-io/uqa/commit/9e024d1a8e76696f818d3fd83f848ace2a0afacb"
        },
        "date": 1773322852454,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 20020.578082644104,
            "unit": "iter/sec",
            "range": "stddev: 0.0000021810670707315785",
            "extra": "mean: 49.94860767116924 usec\nrounds: 3650"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 6576.940806447194,
            "unit": "iter/sec",
            "range": "stddev: 0.000005132493359757276",
            "extra": "mean: 152.04637375171865 usec\nrounds: 3505"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 10199.040372782632,
            "unit": "iter/sec",
            "range": "stddev: 0.000006311508664257678",
            "extra": "mean: 98.0484401913557 usec\nrounds: 5434"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 4330.556661244748,
            "unit": "iter/sec",
            "range": "stddev: 0.0000074344120497642206",
            "extra": "mean: 230.91719569201206 usec\nrounds: 2739"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 9763.214066888795,
            "unit": "iter/sec",
            "range": "stddev: 0.000004048825232806088",
            "extra": "mean: 102.42528670875143 usec\nrounds: 6034"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 5440.566907013004,
            "unit": "iter/sec",
            "range": "stddev: 0.00007416185707031745",
            "extra": "mean: 183.80437500198354 usec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 1732.564037379801,
            "unit": "iter/sec",
            "range": "stddev: 0.000025887216703661978",
            "extra": "mean: 577.179243263253 usec\nrounds: 1336"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4720.253356733379,
            "unit": "iter/sec",
            "range": "stddev: 0.000027403423337655863",
            "extra": "mean: 211.8530350862445 usec\nrounds: 57"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 5927.324466782079,
            "unit": "iter/sec",
            "range": "stddev: 0.000023963427333295876",
            "extra": "mean: 168.71018376068352 usec\nrounds: 234"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 4355.714185500616,
            "unit": "iter/sec",
            "range": "stddev: 0.00026178629821380415",
            "extra": "mean: 229.58347527228003 usec\nrounds: 3215"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 10803.192409358848,
            "unit": "iter/sec",
            "range": "stddev: 0.000004178836193817288",
            "extra": "mean: 92.56523091578893 usec\nrounds: 5777"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 8113.031659277807,
            "unit": "iter/sec",
            "range": "stddev: 0.000011555532439326319",
            "extra": "mean: 123.2584860995127 usec\nrounds: 4748"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 7017.649773020984,
            "unit": "iter/sec",
            "range": "stddev: 0.000012107737102995942",
            "extra": "mean: 142.49784932905197 usec\nrounds: 3949"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 6263.648494257546,
            "unit": "iter/sec",
            "range": "stddev: 0.000012240485176572674",
            "extra": "mean: 159.65135989300657 usec\nrounds: 4104"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 4004.4155721377456,
            "unit": "iter/sec",
            "range": "stddev: 0.000010137394080348765",
            "extra": "mean: 249.72433105042415 usec\nrounds: 876"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1508.1449256932883,
            "unit": "iter/sec",
            "range": "stddev: 0.0000420356081697845",
            "extra": "mean: 663.0662497772248 usec\nrounds: 1121"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 10546.608742135786,
            "unit": "iter/sec",
            "range": "stddev: 0.000008201660655089605",
            "extra": "mean: 94.81720849326688 usec\nrounds: 4168"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 9274.190643054406,
            "unit": "iter/sec",
            "range": "stddev: 0.000004154328966534725",
            "extra": "mean: 107.82612073528125 usec\nrounds: 6419"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 4069.286085557762,
            "unit": "iter/sec",
            "range": "stddev: 0.000010184818574234588",
            "extra": "mean: 245.74335128441425 usec\nrounds: 2024"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 5824.166624667072,
            "unit": "iter/sec",
            "range": "stddev: 0.000014016380934467095",
            "extra": "mean: 171.69838441172058 usec\nrounds: 4157"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 4070.2702410661423,
            "unit": "iter/sec",
            "range": "stddev: 0.000012143298854661715",
            "extra": "mean: 245.6839327056736 usec\nrounds: 2868"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1885.4664766925268,
            "unit": "iter/sec",
            "range": "stddev: 0.00001700370635322431",
            "extra": "mean: 530.3727286385879 usec\nrounds: 1065"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1546.5865942509322,
            "unit": "iter/sec",
            "range": "stddev: 0.0005463649423990332",
            "extra": "mean: 646.5851984733748 usec\nrounds: 1048"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1550.898576392099,
            "unit": "iter/sec",
            "range": "stddev: 0.0003866514128719647",
            "extra": "mean: 644.7874897959668 usec\nrounds: 8036"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 2067.382358481219,
            "unit": "iter/sec",
            "range": "stddev: 0.00002364822652952615",
            "extra": "mean: 483.7034600288645 usec\nrounds: 1376"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 1571.994856062566,
            "unit": "iter/sec",
            "range": "stddev: 0.000019369520116386443",
            "extra": "mean: 636.1343970963984 usec\nrounds: 1171"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 97.22309492327392,
            "unit": "iter/sec",
            "range": "stddev: 0.0027127447782494484",
            "extra": "mean: 10.285621958333824 msec\nrounds: 96"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 98.55505418074151,
            "unit": "iter/sec",
            "range": "stddev: 0.0027767138803306193",
            "extra": "mean: 10.1466130612245 msec\nrounds: 98"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 135.6574322900168,
            "unit": "iter/sec",
            "range": "stddev: 0.0032469091322497867",
            "extra": "mean: 7.371509125000528 msec\nrounds: 136"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 178.07745918938082,
            "unit": "iter/sec",
            "range": "stddev: 0.0029526096645121763",
            "extra": "mean: 5.615533850000216 msec\nrounds: 180"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 181.3270543946041,
            "unit": "iter/sec",
            "range": "stddev: 0.0017880138551097631",
            "extra": "mean: 5.514896843930411 msec\nrounds: 173"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 125.24954650348597,
            "unit": "iter/sec",
            "range": "stddev: 0.0025357264781534048",
            "extra": "mean: 7.9840608442615615 msec\nrounds: 122"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 283.40336752228654,
            "unit": "iter/sec",
            "range": "stddev: 0.0015151613262077768",
            "extra": "mean: 3.5285395820900436 msec\nrounds: 201"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 74.54789931178104,
            "unit": "iter/sec",
            "range": "stddev: 0.0017518742482313262",
            "extra": "mean: 13.41419421917858 msec\nrounds: 73"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10538176759445254,
            "unit": "iter/sec",
            "range": "stddev: 0.07698977504483827",
            "extra": "mean: 9.4893075228 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 16.515978730459867,
            "unit": "iter/sec",
            "range": "stddev: 0.000264869690074011",
            "extra": "mean: 60.54742599999439 msec\nrounds: 17"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 57.20337466313536,
            "unit": "iter/sec",
            "range": "stddev: 0.004349257676646452",
            "extra": "mean: 17.481486116665224 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 73.55291134981411,
            "unit": "iter/sec",
            "range": "stddev: 0.004070455295150948",
            "extra": "mean: 13.595654905406098 msec\nrounds: 74"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 173.40370976488393,
            "unit": "iter/sec",
            "range": "stddev: 0.0013497719833190506",
            "extra": "mean: 5.766889309091994 msec\nrounds: 165"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 145.49596007124708,
            "unit": "iter/sec",
            "range": "stddev: 0.0019397873058382847",
            "extra": "mean: 6.8730430694454725 msec\nrounds: 144"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 394.00537541429577,
            "unit": "iter/sec",
            "range": "stddev: 0.00002125427514680231",
            "extra": "mean: 2.538036439093 msec\nrounds: 353"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 2193.985200312857,
            "unit": "iter/sec",
            "range": "stddev: 0.000054592292594180874",
            "extra": "mean: 455.79158868409974 usec\nrounds: 1573"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 534.5132229947574,
            "unit": "iter/sec",
            "range": "stddev: 0.00119736883788685",
            "extra": "mean: 1.8708611068538676 msec\nrounds: 496"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 252.19454635082423,
            "unit": "iter/sec",
            "range": "stddev: 0.0026497109750528436",
            "extra": "mean: 3.965192802420534 msec\nrounds: 248"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 236.9587883924154,
            "unit": "iter/sec",
            "range": "stddev: 0.0027659624376639522",
            "extra": "mean: 4.220143117646056 msec\nrounds: 238"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1703.5365977449326,
            "unit": "iter/sec",
            "range": "stddev: 0.000013483672312642395",
            "extra": "mean: 587.014098390229 usec\nrounds: 1118"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 139.14090785824712,
            "unit": "iter/sec",
            "range": "stddev: 0.004224755902825589",
            "extra": "mean: 7.186959000000002 msec\nrounds: 150"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 246.92870493253216,
            "unit": "iter/sec",
            "range": "stddev: 0.0028441618253633276",
            "extra": "mean: 4.0497519325395075 msec\nrounds: 252"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 74.4860665739701,
            "unit": "iter/sec",
            "range": "stddev: 0.0039649462087593115",
            "extra": "mean: 13.425329675677354 msec\nrounds: 74"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 59.74369254643641,
            "unit": "iter/sec",
            "range": "stddev: 0.0037516027108129616",
            "extra": "mean: 16.738168622951108 msec\nrounds: 61"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 91.75661735919523,
            "unit": "iter/sec",
            "range": "stddev: 0.001686873043062853",
            "extra": "mean: 10.89839652747167 msec\nrounds: 91"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 58.13204076861564,
            "unit": "iter/sec",
            "range": "stddev: 0.003676184290928886",
            "extra": "mean: 17.20221734482579 msec\nrounds: 29"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 103.77521822318839,
            "unit": "iter/sec",
            "range": "stddev: 0.0024563404014179215",
            "extra": "mean: 9.636211969695013 msec\nrounds: 99"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 99.58670761578051,
            "unit": "iter/sec",
            "range": "stddev: 0.0025545437538521633",
            "extra": "mean: 10.041500757893717 msec\nrounds: 95"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 86.69203009481058,
            "unit": "iter/sec",
            "range": "stddev: 0.00402187177890786",
            "extra": "mean: 11.535085738635397 msec\nrounds: 88"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 181.0775430759116,
            "unit": "iter/sec",
            "range": "stddev: 0.0026574903156940423",
            "extra": "mean: 5.522495959539159 msec\nrounds: 173"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 163.4883262283027,
            "unit": "iter/sec",
            "range": "stddev: 0.003440888552603357",
            "extra": "mean: 6.116644674700219 msec\nrounds: 166"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 169.31456563001686,
            "unit": "iter/sec",
            "range": "stddev: 0.0015227423626000328",
            "extra": "mean: 5.90616640853677 msec\nrounds: 164"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 145.88245517579364,
            "unit": "iter/sec",
            "range": "stddev: 0.001998858992390905",
            "extra": "mean: 6.854833905797403 msec\nrounds: 138"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 40.37302492921905,
            "unit": "iter/sec",
            "range": "stddev: 0.00017195561307416606",
            "extra": "mean: 24.7690135121947 msec\nrounds: 41"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 250.0778507314516,
            "unit": "iter/sec",
            "range": "stddev: 0.0027394330758439014",
            "extra": "mean: 3.9987547760631514 msec\nrounds: 259"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 248.77533998034653,
            "unit": "iter/sec",
            "range": "stddev: 0.002741260712211021",
            "extra": "mean: 4.0196910195319235 msec\nrounds: 256"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 78.96425866065728,
            "unit": "iter/sec",
            "range": "stddev: 0.004472688209153053",
            "extra": "mean: 12.663957301206635 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 83.75690943165073,
            "unit": "iter/sec",
            "range": "stddev: 0.0033739631858180174",
            "extra": "mean: 11.939313506022371 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 637415.0720359607,
            "unit": "iter/sec",
            "range": "stddev: 2.557901949073723e-7",
            "extra": "mean: 1.5688364518992475 usec\nrounds: 57078"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 270225.50203913625,
            "unit": "iter/sec",
            "range": "stddev: 4.347596689583233e-7",
            "extra": "mean: 3.700612978619508 usec\nrounds: 66756"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 85863.62887115251,
            "unit": "iter/sec",
            "range": "stddev: 7.000814238702986e-7",
            "extra": "mean: 11.64637475898679 usec\nrounds: 33699"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 775445.1402711762,
            "unit": "iter/sec",
            "range": "stddev: 2.35124258605214e-7",
            "extra": "mean: 1.2895818776429444 usec\nrounds: 98464"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2369648.9339423077,
            "unit": "iter/sec",
            "range": "stddev: 2.9154894719876713e-8",
            "extra": "mean: 422.00343927584777 nsec\nrounds: 111099"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1429929.611843493,
            "unit": "iter/sec",
            "range": "stddev: 1.4918590047414644e-7",
            "extra": "mean: 699.3351223147135 nsec\nrounds: 189862"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2620374.743160033,
            "unit": "iter/sec",
            "range": "stddev: 2.967717156738119e-8",
            "extra": "mean: 381.62480485293224 nsec\nrounds: 130158"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 179596.3435494846,
            "unit": "iter/sec",
            "range": "stddev: 4.442580454360796e-7",
            "extra": "mean: 5.568042089478663 usec\nrounds: 83964"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1729.8595584066488,
            "unit": "iter/sec",
            "range": "stddev: 0.000018640576745774756",
            "extra": "mean: 578.081610810699 usec\nrounds: 1480"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1741.919408336608,
            "unit": "iter/sec",
            "range": "stddev: 0.000018794377397745152",
            "extra": "mean: 574.0793719928289 usec\nrounds: 1621"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 446243.3329886843,
            "unit": "iter/sec",
            "range": "stddev: 4.474869302799719e-7",
            "extra": "mean: 2.2409298382175664 usec\nrounds: 69411"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 207166.87200697575,
            "unit": "iter/sec",
            "range": "stddev: 4.5504905478316677e-7",
            "extra": "mean: 4.8270265912318635 usec\nrounds: 54642"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 126271.80418130034,
            "unit": "iter/sec",
            "range": "stddev: 6.752934748370104e-7",
            "extra": "mean: 7.919424344046004 usec\nrounds: 51873"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 347827.15356410004,
            "unit": "iter/sec",
            "range": "stddev: 3.9365334324832707e-7",
            "extra": "mean: 2.8749911838487705 usec\nrounds: 90515"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 111671.66353638815,
            "unit": "iter/sec",
            "range": "stddev: 6.696277030979484e-7",
            "extra": "mean: 8.95482316939024 usec\nrounds: 50325"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 17313.14912010616,
            "unit": "iter/sec",
            "range": "stddev: 0.0000021569937678366333",
            "extra": "mean: 57.759567197320365 usec\nrounds: 7225"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 11238.882328158883,
            "unit": "iter/sec",
            "range": "stddev: 0.00000266830614486448",
            "extra": "mean: 88.97681911790394 usec\nrounds: 7574"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 13404.705858481206,
            "unit": "iter/sec",
            "range": "stddev: 0.000003077155678184171",
            "extra": "mean: 74.60066715058103 usec\nrounds: 8265"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 103459.26231752486,
            "unit": "iter/sec",
            "range": "stddev: 8.286653775309933e-7",
            "extra": "mean: 9.665640152458453 usec\nrounds: 30713"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 29725.081559733804,
            "unit": "iter/sec",
            "range": "stddev: 0.0000016021097060926158",
            "extra": "mean: 33.64162342130022 usec\nrounds: 15362"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 6989.716872070865,
            "unit": "iter/sec",
            "range": "stddev: 0.000005619720315556125",
            "extra": "mean: 143.06731135215878 usec\nrounds: 4519"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2495.0549227738024,
            "unit": "iter/sec",
            "range": "stddev: 0.000006610072191516134",
            "extra": "mean: 400.79278050051096 usec\nrounds: 1918"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 102439.72095822834,
            "unit": "iter/sec",
            "range": "stddev: 9.348312302811707e-7",
            "extra": "mean: 9.761838383060104 usec\nrounds: 36735"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 20361.523745753053,
            "unit": "iter/sec",
            "range": "stddev: 0.000003402579348923542",
            "extra": "mean: 49.11223798801291 usec\nrounds: 11530"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1519.2889377673557,
            "unit": "iter/sec",
            "range": "stddev: 0.000009832153010331007",
            "extra": "mean: 658.2026467391596 usec\nrounds: 552"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 209.35386306832055,
            "unit": "iter/sec",
            "range": "stddev: 0.00038415011427317766",
            "extra": "mean: 4.776601612904845 msec\nrounds: 186"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.47623428666066436,
            "unit": "iter/sec",
            "range": "stddev: 0.005325257665774095",
            "extra": "mean: 2.099806813600003 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 80813.93557725723,
            "unit": "iter/sec",
            "range": "stddev: 9.71167187763444e-7",
            "extra": "mean: 12.374103461945756 usec\nrounds: 27846"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 7595.738924185564,
            "unit": "iter/sec",
            "range": "stddev: 0.000003007055622061865",
            "extra": "mean: 131.65276084146387 usec\nrounds: 5419"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 181.19899820272494,
            "unit": "iter/sec",
            "range": "stddev: 0.000058685980273747705",
            "extra": "mean: 5.5187943085711915 msec\nrounds: 175"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 80990.53273331732,
            "unit": "iter/sec",
            "range": "stddev: 8.9116286671848e-7",
            "extra": "mean: 12.347122141951624 usec\nrounds: 33240"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 16865.534817396794,
            "unit": "iter/sec",
            "range": "stddev: 0.0000021995740966457255",
            "extra": "mean: 59.29251641451064 usec\nrounds: 10052"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 3083.3995704349513,
            "unit": "iter/sec",
            "range": "stddev: 0.000006726134299791075",
            "extra": "mean: 324.3173572405141 usec\nrounds: 2189"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 913.5783327932887,
            "unit": "iter/sec",
            "range": "stddev: 0.000011219565000048983",
            "extra": "mean: 1.0945968879783683 msec\nrounds: 732"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6977.185601693372,
            "unit": "iter/sec",
            "range": "stddev: 0.000005384873295008782",
            "extra": "mean: 143.32426526783217 usec\nrounds: 4765"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1521.3616502657628,
            "unit": "iter/sec",
            "range": "stddev: 0.000007175510059903725",
            "extra": "mean: 657.3059073924419 usec\nrounds: 1231"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 182.09968849838754,
            "unit": "iter/sec",
            "range": "stddev: 0.00003047661427552952",
            "extra": "mean: 5.4914975870969425 msec\nrounds: 155"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 3063.381859174987,
            "unit": "iter/sec",
            "range": "stddev: 0.000008401503189227058",
            "extra": "mean: 326.43661351096284 usec\nrounds: 2176"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 66.17741789850814,
            "unit": "iter/sec",
            "range": "stddev: 0.000059290372411830123",
            "extra": "mean: 15.110894800000096 msec\nrounds: 65"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1353.6673709919346,
            "unit": "iter/sec",
            "range": "stddev: 0.000009534066483145377",
            "extra": "mean: 738.7339175260051 usec\nrounds: 1261"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 440.90550088485674,
            "unit": "iter/sec",
            "range": "stddev: 0.000022653656428580676",
            "extra": "mean: 2.2680597043881106 msec\nrounds: 433"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1599.1261711143156,
            "unit": "iter/sec",
            "range": "stddev: 0.000010570355554902603",
            "extra": "mean: 625.341525930485 usec\nrounds: 1504"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 534.4931568272393,
            "unit": "iter/sec",
            "range": "stddev: 0.000017704887744444753",
            "extra": "mean: 1.8709313435105837 msec\nrounds: 524"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 395.2399886416564,
            "unit": "iter/sec",
            "range": "stddev: 0.0000317924585639832",
            "extra": "mean: 2.530108361344601 msec\nrounds: 357"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1713.571828612143,
            "unit": "iter/sec",
            "range": "stddev: 0.000013903523698317112",
            "extra": "mean: 583.5763539658099 usec\nrounds: 1034"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1367.84750889669,
            "unit": "iter/sec",
            "range": "stddev: 0.000018223453235812794",
            "extra": "mean: 731.0756451255323 usec\nrounds: 913"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 949.4787447125419,
            "unit": "iter/sec",
            "range": "stddev: 0.001238622269611482",
            "extra": "mean: 1.0532094642126544 msec\nrounds: 978"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 67.64287457340768,
            "unit": "iter/sec",
            "range": "stddev: 0.010483204654801376",
            "extra": "mean: 14.78352311764598 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 5.692678883215184,
            "unit": "iter/sec",
            "range": "stddev: 0.046941084019879044",
            "extra": "mean: 175.66422075000432 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 301.17777894756694,
            "unit": "iter/sec",
            "range": "stddev: 0.00002321424997784019",
            "extra": "mean: 3.320298076087789 msec\nrounds: 276"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 70.22846007579156,
            "unit": "iter/sec",
            "range": "stddev: 0.009838412321404538",
            "extra": "mean: 14.239241454544006 msec\nrounds: 88"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 33.44677318836427,
            "unit": "iter/sec",
            "range": "stddev: 0.01511848519606418",
            "extra": "mean: 29.898250404253886 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 23.602663185258418,
            "unit": "iter/sec",
            "range": "stddev: 0.017657000426794536",
            "extra": "mean: 42.36810024999945 msec\nrounds: 36"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 980.6151692836572,
            "unit": "iter/sec",
            "range": "stddev: 0.0012612880504204375",
            "extra": "mean: 1.0197680306439716 msec\nrounds: 979"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 71.33197407214438,
            "unit": "iter/sec",
            "range": "stddev: 0.010048360946423321",
            "extra": "mean: 14.018958720932227 msec\nrounds: 86"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 6.1771405042108505,
            "unit": "iter/sec",
            "range": "stddev: 0.04126092377762717",
            "extra": "mean: 161.88720319997856 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 328.9060342255874,
            "unit": "iter/sec",
            "range": "stddev: 0.00002671461458197638",
            "extra": "mean: 3.040382042106677 msec\nrounds: 285"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 67.280565732406,
            "unit": "iter/sec",
            "range": "stddev: 0.011002386975233671",
            "extra": "mean: 14.863133047621583 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 34.134491418012004,
            "unit": "iter/sec",
            "range": "stddev: 0.014719357276717759",
            "extra": "mean: 29.29588104167043 msec\nrounds: 48"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 24.08498001539145,
            "unit": "iter/sec",
            "range": "stddev: 0.01729755538081407",
            "extra": "mean: 41.519652470583424 msec\nrounds: 17"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 17461.050206495587,
            "unit": "iter/sec",
            "range": "stddev: 0.00000194966936673684",
            "extra": "mean: 57.27032384501109 usec\nrounds: 9872"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 1049.7470184933613,
            "unit": "iter/sec",
            "range": "stddev: 0.000008490121148048563",
            "extra": "mean: 952.6104693635995 usec\nrounds: 865"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 68.52704148504215,
            "unit": "iter/sec",
            "range": "stddev: 0.0018113886276617604",
            "extra": "mean: 14.592779409837455 msec\nrounds: 61"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1156.2820511492587,
            "unit": "iter/sec",
            "range": "stddev: 0.000011159878838945137",
            "extra": "mean: 864.8408915507027 usec\nrounds: 793"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 1038.9625525264344,
            "unit": "iter/sec",
            "range": "stddev: 0.000009166274252181078",
            "extra": "mean: 962.4985978256007 usec\nrounds: 736"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 1025.2335096389584,
            "unit": "iter/sec",
            "range": "stddev: 0.000013469438613709466",
            "extra": "mean: 975.3875488835275 usec\nrounds: 716"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 1062.6826866942556,
            "unit": "iter/sec",
            "range": "stddev: 0.0000196032843321066",
            "extra": "mean: 941.014672132049 usec\nrounds: 732"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 188.08474461999484,
            "unit": "iter/sec",
            "range": "stddev: 0.00019945708355271694",
            "extra": "mean: 5.316752307691904 msec\nrounds: 169"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 193.98735179617663,
            "unit": "iter/sec",
            "range": "stddev: 0.00024998361782339304",
            "extra": "mean: 5.154975263803305 msec\nrounds: 163"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 112.42588790881723,
            "unit": "iter/sec",
            "range": "stddev: 0.00017876908077078544",
            "extra": "mean: 8.894748519229378 msec\nrounds: 104"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 63.74960173781359,
            "unit": "iter/sec",
            "range": "stddev: 0.010882806954980291",
            "extra": "mean: 15.686372506494294 msec\nrounds: 77"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 17.857169337307173,
            "unit": "iter/sec",
            "range": "stddev: 0.019666606380854195",
            "extra": "mean: 55.999916958327844 msec\nrounds: 24"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 6.465376205408514,
            "unit": "iter/sec",
            "range": "stddev: 0.023810137783752724",
            "extra": "mean: 154.67004057141563 msec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.1508224523308597,
            "unit": "iter/sec",
            "range": "stddev: 0.0099703024750899",
            "extra": "mean: 464.93842339998537 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 43.12511198378287,
            "unit": "iter/sec",
            "range": "stddev: 0.013720263354128853",
            "extra": "mean: 23.18834558333549 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 14.830242588016786,
            "unit": "iter/sec",
            "range": "stddev: 0.01963307483331414",
            "extra": "mean: 67.4297803333322 msec\nrounds: 12"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 6.385616235228464,
            "unit": "iter/sec",
            "range": "stddev: 0.01677187189068442",
            "extra": "mean: 156.60195714286016 msec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 3.216846173567094,
            "unit": "iter/sec",
            "range": "stddev: 0.03693672142924173",
            "extra": "mean: 310.8634812000105 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 44.92390958596121,
            "unit": "iter/sec",
            "range": "stddev: 0.013234979022047101",
            "extra": "mean: 22.25986137930661 msec\nrounds: 58"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 498020.1487900095,
            "unit": "iter/sec",
            "range": "stddev: 2.507373616123437e-7",
            "extra": "mean: 2.0079508879903782 usec\nrounds: 77598"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1502995.8983091235,
            "unit": "iter/sec",
            "range": "stddev: 1.6142432363387365e-7",
            "extra": "mean: 665.3378103859126 nsec\nrounds: 97685"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 131.617381821809,
            "unit": "iter/sec",
            "range": "stddev: 0.000032584922875778935",
            "extra": "mean: 7.597780674241462 msec\nrounds: 132"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3766807.3831902547,
            "unit": "iter/sec",
            "range": "stddev: 2.453469632040049e-8",
            "extra": "mean: 265.47680788314193 nsec\nrounds: 180930"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4513935.611210082,
            "unit": "iter/sec",
            "range": "stddev: 1.918013576749751e-8",
            "extra": "mean: 221.53616846384816 nsec\nrounds: 194932"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4271292.897976078,
            "unit": "iter/sec",
            "range": "stddev: 2.345461422639843e-8",
            "extra": "mean: 234.12114876829048 nsec\nrounds: 197942"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 4130225.736429492,
            "unit": "iter/sec",
            "range": "stddev: 1.9296973278890675e-8",
            "extra": "mean: 242.1175170111846 nsec\nrounds: 189359"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3627250.456577517,
            "unit": "iter/sec",
            "range": "stddev: 2.218856036579446e-8",
            "extra": "mean: 275.6909157421535 nsec\nrounds: 189970"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 32285.585058032506,
            "unit": "iter/sec",
            "range": "stddev: 0.0000017808397181674248",
            "extra": "mean: 30.973575303112078 usec\nrounds: 5604"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 32.143990020219235,
            "unit": "iter/sec",
            "range": "stddev: 0.00007790760564519159",
            "extra": "mean: 31.110014636359058 msec\nrounds: 33"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 7696240.8913896205,
            "unit": "iter/sec",
            "range": "stddev: 8.477320341245356e-9",
            "extra": "mean: 129.93356290585672 nsec\nrounds: 76853"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 38067.49961682293,
            "unit": "iter/sec",
            "range": "stddev: 0.0000017876551469444828",
            "extra": "mean: 26.269127472666376 usec\nrounds: 12740"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 37748.415677342746,
            "unit": "iter/sec",
            "range": "stddev: 0.000001830675091853185",
            "extra": "mean: 26.49117802843888 usec\nrounds: 14200"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 37538.66119562717,
            "unit": "iter/sec",
            "range": "stddev: 0.000001631791710116025",
            "extra": "mean: 26.63920257541014 usec\nrounds: 14444"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 206596.48461517325,
            "unit": "iter/sec",
            "range": "stddev: 4.987477837562884e-7",
            "extra": "mean: 4.840353415803263 usec\nrounds: 83655"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 206436.23063772157,
            "unit": "iter/sec",
            "range": "stddev: 5.06417913373841e-7",
            "extra": "mean: 4.844110924283039 usec\nrounds: 112969"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 205589.7257818009,
            "unit": "iter/sec",
            "range": "stddev: 5.522315833960436e-7",
            "extra": "mean: 4.864056295601721 usec\nrounds: 115835"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 197206.49549837603,
            "unit": "iter/sec",
            "range": "stddev: 8.940081005333608e-7",
            "extra": "mean: 5.070826888702735 usec\nrounds: 24516"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 214.2296837405762,
            "unit": "iter/sec",
            "range": "stddev: 0.000042190967437558965",
            "extra": "mean: 4.667887206569194 msec\nrounds: 213"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 37867.632556445096,
            "unit": "iter/sec",
            "range": "stddev: 0.0000015386732122315223",
            "extra": "mean: 26.40777710382107 usec\nrounds: 10211"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 37898.03747416323,
            "unit": "iter/sec",
            "range": "stddev: 0.0000016649715715633504",
            "extra": "mean: 26.386590616512642 usec\nrounds: 13364"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 37561.72623820448,
            "unit": "iter/sec",
            "range": "stddev: 0.0000022690610184566772",
            "extra": "mean: 26.622844585425046 usec\nrounds: 14471"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 37222.980841509656,
            "unit": "iter/sec",
            "range": "stddev: 0.0000016580717610900961",
            "extra": "mean: 26.865124108621576 usec\nrounds: 13883"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.8345383775369326,
            "unit": "iter/sec",
            "range": "stddev: 0.00034768294626046455",
            "extra": "mean: 260.7875841999885 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 30161.68504326494,
            "unit": "iter/sec",
            "range": "stddev: 0.000002153857424994569",
            "extra": "mean: 33.15464631918164 usec\nrounds: 9223"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 30197.50447216462,
            "unit": "iter/sec",
            "range": "stddev: 0.0000018165874696060765",
            "extra": "mean: 33.11531921194936 usec\nrounds: 12487"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 30063.22621250734,
            "unit": "iter/sec",
            "range": "stddev: 0.000001736160694903397",
            "extra": "mean: 33.263229732275555 usec\nrounds: 10756"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 173074.8885579148,
            "unit": "iter/sec",
            "range": "stddev: 6.265050548571146e-7",
            "extra": "mean: 5.77784569634651 usec\nrounds: 34134"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 18889.371661579513,
            "unit": "iter/sec",
            "range": "stddev: 0.0000021521657315502853",
            "extra": "mean: 52.939823405241896 usec\nrounds: 13262"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1900.1117962534174,
            "unit": "iter/sec",
            "range": "stddev: 0.0000097330886870539",
            "extra": "mean: 526.2848228045158 usec\nrounds: 1868"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 198052.64159501763,
            "unit": "iter/sec",
            "range": "stddev: 7.241749369956775e-7",
            "extra": "mean: 5.0491626465897985 usec\nrounds: 26659"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 2969.877218705332,
            "unit": "iter/sec",
            "range": "stddev: 0.000005119384826333399",
            "extra": "mean: 336.71425663715934 usec\nrounds: 2260"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 1621.7864928636827,
            "unit": "iter/sec",
            "range": "stddev: 0.001165279196226861",
            "extra": "mean: 616.6039761708965 usec\nrounds: 1217"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 591.3565180929194,
            "unit": "iter/sec",
            "range": "stddev: 0.0024335971509768404",
            "extra": "mean: 1.6910272727269928 msec\nrounds: 561"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 56046.80922195352,
            "unit": "iter/sec",
            "range": "stddev: 0.0000015381928499909554",
            "extra": "mean: 17.84222891333304 usec\nrounds: 11109"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 29.41707254822031,
            "unit": "iter/sec",
            "range": "stddev: 0.0006401773092625092",
            "extra": "mean: 33.99386524137659 msec\nrounds: 29"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 26775.68620943823,
            "unit": "iter/sec",
            "range": "stddev: 0.000002204103968414829",
            "extra": "mean: 37.347315477857194 usec\nrounds: 9297"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 9288.957811792552,
            "unit": "iter/sec",
            "range": "stddev: 0.000004387125943311404",
            "extra": "mean: 107.65470360199895 usec\nrounds: 5108"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 13190.18803504215,
            "unit": "iter/sec",
            "range": "stddev: 0.0000024784616020439148",
            "extra": "mean: 75.81393057804156 usec\nrounds: 8614"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3652.8601245246346,
            "unit": "iter/sec",
            "range": "stddev: 0.0001215450266956546",
            "extra": "mean: 273.75808706338984 usec\nrounds: 2010"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 1633465.0500186456,
            "unit": "iter/sec",
            "range": "stddev: 1.503884121666249e-7",
            "extra": "mean: 612.1955287556261 nsec\nrounds: 189251"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1545682.450668024,
            "unit": "iter/sec",
            "range": "stddev: 1.5691199253898765e-7",
            "extra": "mean: 646.9634170769118 nsec\nrounds: 185633"
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
          "id": "6b8bf7021157efd7184ea431f24d8daa476e01fc",
          "message": "Bump version to 0.12.0",
          "timestamp": "2026-03-12T23:47:25+09:00",
          "tree_id": "31f8d69cadfcfedd2ffb13161b9a5d5032c193d4",
          "url": "https://github.com/cognica-io/uqa/commit/6b8bf7021157efd7184ea431f24d8daa476e01fc"
        },
        "date": 1773327225566,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 17139.77522194992,
            "unit": "iter/sec",
            "range": "stddev: 0.000004816138630642526",
            "extra": "mean: 58.343822311004274 usec\nrounds: 2752"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 5594.075069380213,
            "unit": "iter/sec",
            "range": "stddev: 0.000008802348007623559",
            "extra": "mean: 178.76056141498893 usec\nrounds: 3053"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 8725.211909959438,
            "unit": "iter/sec",
            "range": "stddev: 0.00000669964342619035",
            "extra": "mean: 114.61039689575274 usec\nrounds: 5412"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 3657.250898389001,
            "unit": "iter/sec",
            "range": "stddev: 0.000010694008343897694",
            "extra": "mean: 273.42942220357224 usec\nrounds: 2378"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 8223.862147377455,
            "unit": "iter/sec",
            "range": "stddev: 0.000006688710754174058",
            "extra": "mean: 121.59736898300206 usec\nrounds: 5152"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 4506.575093132805,
            "unit": "iter/sec",
            "range": "stddev: 0.00008222323181131883",
            "extra": "mean: 221.8979999964534 usec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 1541.8391757198674,
            "unit": "iter/sec",
            "range": "stddev: 0.00004875854595114355",
            "extra": "mean: 648.5760744359808 usec\nrounds: 1330"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 3825.299803420047,
            "unit": "iter/sec",
            "range": "stddev: 0.00005730180118857291",
            "extra": "mean: 261.4174186049261 usec\nrounds: 43"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 4940.278868863227,
            "unit": "iter/sec",
            "range": "stddev: 0.00002179375989657196",
            "extra": "mean: 202.41772307685596 usec\nrounds: 195"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 3669.2492371506346,
            "unit": "iter/sec",
            "range": "stddev: 0.000019649120002295598",
            "extra": "mean: 272.5353159101704 usec\nrounds: 2181"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 9180.555705094293,
            "unit": "iter/sec",
            "range": "stddev: 0.000007059904942005927",
            "extra": "mean: 108.92586811984592 usec\nrounds: 5505"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 6673.483551768941,
            "unit": "iter/sec",
            "range": "stddev: 0.0002081311902562009",
            "extra": "mean: 149.84677676098113 usec\nrounds: 4699"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 5821.08684187343,
            "unit": "iter/sec",
            "range": "stddev: 0.00001824154913232077",
            "extra": "mean: 171.78922547703567 usec\nrounds: 3721"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 5239.044456926582,
            "unit": "iter/sec",
            "range": "stddev: 0.000018173821869927383",
            "extra": "mean: 190.87450168091092 usec\nrounds: 3867"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 3230.1488695756966,
            "unit": "iter/sec",
            "range": "stddev: 0.000016343285440308247",
            "extra": "mean: 309.5832546353683 usec\nrounds: 809"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1251.8876835284095,
            "unit": "iter/sec",
            "range": "stddev: 0.00003170375546910603",
            "extra": "mean: 798.7937042255489 usec\nrounds: 994"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 8709.963514635685,
            "unit": "iter/sec",
            "range": "stddev: 0.000010475225020284226",
            "extra": "mean: 114.81104350433405 usec\nrounds: 5034"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 7728.6804238188915,
            "unit": "iter/sec",
            "range": "stddev: 0.0000093659935550333",
            "extra": "mean: 129.3881937359082 usec\nrounds: 5332"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 3427.2710122296717,
            "unit": "iter/sec",
            "range": "stddev: 0.0000154299403396672",
            "extra": "mean: 291.7773343373369 usec\nrounds: 1992"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 4982.315451304452,
            "unit": "iter/sec",
            "range": "stddev: 0.000018978412329230242",
            "extra": "mean: 200.70989277448973 usec\nrounds: 3889"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 3415.9053642216622,
            "unit": "iter/sec",
            "range": "stddev: 0.00001952950316494837",
            "extra": "mean: 292.7481570403099 usec\nrounds: 2649"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1759.482463884633,
            "unit": "iter/sec",
            "range": "stddev: 0.000022159217649114544",
            "extra": "mean: 568.3489438094047 usec\nrounds: 1050"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1416.589174901012,
            "unit": "iter/sec",
            "range": "stddev: 0.000628755337267577",
            "extra": "mean: 705.9209668673896 usec\nrounds: 996"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1727.2737006695215,
            "unit": "iter/sec",
            "range": "stddev: 0.00047162573311183956",
            "extra": "mean: 578.9470421580451 usec\nrounds: 6191"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 1894.8312808958271,
            "unit": "iter/sec",
            "range": "stddev: 0.00003173462165875706",
            "extra": "mean: 527.7514732220517 usec\nrounds: 1139"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 1399.52056234073,
            "unit": "iter/sec",
            "range": "stddev: 0.000021508537626822677",
            "extra": "mean: 714.5304091334515 usec\nrounds: 1073"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 91.64877372017611,
            "unit": "iter/sec",
            "range": "stddev: 0.004059373868835675",
            "extra": "mean: 10.91122073333158 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 96.62078829663885,
            "unit": "iter/sec",
            "range": "stddev: 0.003128158402281729",
            "extra": "mean: 10.349739612244367 msec\nrounds: 98"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 115.73735272997047,
            "unit": "iter/sec",
            "range": "stddev: 0.005372654218033073",
            "extra": "mean: 8.640252921052406 msec\nrounds: 114"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 161.27326481707647,
            "unit": "iter/sec",
            "range": "stddev: 0.0034306079532717784",
            "extra": "mean: 6.20065576978457 msec\nrounds: 139"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 153.04906088221267,
            "unit": "iter/sec",
            "range": "stddev: 0.0031937136498243037",
            "extra": "mean: 6.533852571428746 msec\nrounds: 154"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 109.56252787290805,
            "unit": "iter/sec",
            "range": "stddev: 0.003330732196430022",
            "extra": "mean: 9.12720817431298 msec\nrounds: 109"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 252.7760381230918,
            "unit": "iter/sec",
            "range": "stddev: 0.0021701107211799004",
            "extra": "mean: 3.9560711823208496 msec\nrounds: 181"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 71.49921776280411,
            "unit": "iter/sec",
            "range": "stddev: 0.0026729184316193143",
            "extra": "mean: 13.986167000000775 msec\nrounds: 71"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10256944729915021,
            "unit": "iter/sec",
            "range": "stddev: 0.06291531317318527",
            "extra": "mean: 9.749491942599997 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 13.85915326435966,
            "unit": "iter/sec",
            "range": "stddev: 0.000276737344864373",
            "extra": "mean: 72.15448021428627 msec\nrounds: 14"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 49.01709009643323,
            "unit": "iter/sec",
            "range": "stddev: 0.006671732616678023",
            "extra": "mean: 20.401047839287504 msec\nrounds: 56"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 60.56965875736229,
            "unit": "iter/sec",
            "range": "stddev: 0.006550362677560978",
            "extra": "mean: 16.509916359376042 msec\nrounds: 64"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 155.30701347321724,
            "unit": "iter/sec",
            "range": "stddev: 0.0021223575837798856",
            "extra": "mean: 6.4388592481205 msec\nrounds: 133"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 136.94541062363555,
            "unit": "iter/sec",
            "range": "stddev: 0.002121021072199264",
            "extra": "mean: 7.302179718517773 msec\nrounds: 135"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 340.35349303110456,
            "unit": "iter/sec",
            "range": "stddev: 0.00005052521042178517",
            "extra": "mean: 2.9381217483453623 msec\nrounds: 302"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 1897.0963417483813,
            "unit": "iter/sec",
            "range": "stddev: 0.000021602149289562128",
            "extra": "mean: 527.1213580425709 usec\nrounds: 1349"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 461.0366398986414,
            "unit": "iter/sec",
            "range": "stddev: 0.0016084966480990315",
            "extra": "mean: 2.169025004650063 msec\nrounds: 430"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 218.40012507681698,
            "unit": "iter/sec",
            "range": "stddev: 0.003338756714672913",
            "extra": "mean: 4.578751956521426 msec\nrounds: 230"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 198.95773904975437,
            "unit": "iter/sec",
            "range": "stddev: 0.0037544950281024423",
            "extra": "mean: 5.026193023584395 msec\nrounds: 212"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1568.781753364878,
            "unit": "iter/sec",
            "range": "stddev: 0.00002819889330303701",
            "extra": "mean: 637.4372967145374 usec\nrounds: 974"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 116.17145037695184,
            "unit": "iter/sec",
            "range": "stddev: 0.006108523214062677",
            "extra": "mean: 8.607966903703199 msec\nrounds: 135"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 216.39868869473165,
            "unit": "iter/sec",
            "range": "stddev: 0.0032305327311519397",
            "extra": "mean: 4.621100090909865 msec\nrounds: 198"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 69.18245320717845,
            "unit": "iter/sec",
            "range": "stddev: 0.005137684743315271",
            "extra": "mean: 14.454532235295737 msec\nrounds: 68"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 56.56937129164583,
            "unit": "iter/sec",
            "range": "stddev: 0.004378203599930236",
            "extra": "mean: 17.677410534482643 msec\nrounds: 58"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 82.19205807936223,
            "unit": "iter/sec",
            "range": "stddev: 0.0042229802755504925",
            "extra": "mean: 12.166625625001743 msec\nrounds: 88"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 56.420421001492606,
            "unit": "iter/sec",
            "range": "stddev: 0.005307510578831105",
            "extra": "mean: 17.724079016949286 msec\nrounds: 59"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 95.47045297079183,
            "unit": "iter/sec",
            "range": "stddev: 0.0042768743793382994",
            "extra": "mean: 10.474444908163779 msec\nrounds: 98"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 93.6445943243051,
            "unit": "iter/sec",
            "range": "stddev: 0.003605988104546526",
            "extra": "mean: 10.678672989247534 msec\nrounds: 93"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 80.73473440721351,
            "unit": "iter/sec",
            "range": "stddev: 0.005737325984310989",
            "extra": "mean: 12.386242518073507 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 157.56910275247722,
            "unit": "iter/sec",
            "range": "stddev: 0.0036104957388141605",
            "extra": "mean: 6.346421871620885 msec\nrounds: 148"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 138.1787426871884,
            "unit": "iter/sec",
            "range": "stddev: 0.005137370548300157",
            "extra": "mean: 7.237003178295077 msec\nrounds: 129"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 166.67688385347748,
            "unit": "iter/sec",
            "range": "stddev: 0.0015840736073458423",
            "extra": "mean: 5.999632203821865 msec\nrounds: 157"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 142.00784845478188,
            "unit": "iter/sec",
            "range": "stddev: 0.0014306747075125028",
            "extra": "mean: 7.041864311594158 msec\nrounds: 138"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 38.46347224959189,
            "unit": "iter/sec",
            "range": "stddev: 0.0027864034636856396",
            "extra": "mean: 25.99869282499867 msec\nrounds: 40"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 218.17824635580195,
            "unit": "iter/sec",
            "range": "stddev: 0.00328089753233299",
            "extra": "mean: 4.5834083677124 msec\nrounds: 223"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 213.3496802136973,
            "unit": "iter/sec",
            "range": "stddev: 0.0035711819399536857",
            "extra": "mean: 4.687140843137757 msec\nrounds: 204"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 69.58421053369509,
            "unit": "iter/sec",
            "range": "stddev: 0.0067512859724393704",
            "extra": "mean: 14.371076316454944 msec\nrounds: 79"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 74.85996570048862,
            "unit": "iter/sec",
            "range": "stddev: 0.00503818120232051",
            "extra": "mean: 13.35827488888995 msec\nrounds: 81"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 626021.0696497634,
            "unit": "iter/sec",
            "range": "stddev: 4.0027112801490263e-7",
            "extra": "mean: 1.597390325152258 usec\nrounds: 56745"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 262303.4029400503,
            "unit": "iter/sec",
            "range": "stddev: 6.873120395940274e-7",
            "extra": "mean: 3.8123790571964142 usec\nrounds: 62112"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 78054.01521854999,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011606584418584178",
            "extra": "mean: 12.811640723414627 usec\nrounds: 27920"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 760791.0081358866,
            "unit": "iter/sec",
            "range": "stddev: 3.264059235955713e-7",
            "extra": "mean: 1.3144214236314786 usec\nrounds: 105286"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2157448.538017075,
            "unit": "iter/sec",
            "range": "stddev: 4.7192379390334846e-8",
            "extra": "mean: 463.5104765553789 nsec\nrounds: 104080"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1687850.4901187543,
            "unit": "iter/sec",
            "range": "stddev: 7.737393998698281e-8",
            "extra": "mean: 592.4695379444667 nsec\nrounds: 173914"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2443388.3367945226,
            "unit": "iter/sec",
            "range": "stddev: 4.270108800956662e-8",
            "extra": "mean: 409.2677307741832 nsec\nrounds: 116185"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 179131.63776110663,
            "unit": "iter/sec",
            "range": "stddev: 7.699361822048641e-7",
            "extra": "mean: 5.582486781780107 usec\nrounds: 84013"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1569.1681625226288,
            "unit": "iter/sec",
            "range": "stddev: 0.00012763969823611292",
            "extra": "mean: 637.2803271718044 usec\nrounds: 1082"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1634.6897238949841,
            "unit": "iter/sec",
            "range": "stddev: 0.000019026190444841697",
            "extra": "mean: 611.7368852220435 usec\nrounds: 1394"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 442181.1063984049,
            "unit": "iter/sec",
            "range": "stddev: 5.928703610580155e-7",
            "extra": "mean: 2.261516798275412 usec\nrounds: 65364"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 192325.2415519554,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012102536832990055",
            "extra": "mean: 5.19952551173506 usec\nrounds: 59698"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 116320.15111039007,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010150899576105163",
            "extra": "mean: 8.596962696953348 usec\nrounds: 43991"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 336021.0054329374,
            "unit": "iter/sec",
            "range": "stddev: 5.753564110510345e-7",
            "extra": "mean: 2.9760044277933644 usec\nrounds: 83112"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 101849.95628926683,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010438176005714376",
            "extra": "mean: 9.818364547549464 usec\nrounds: 42801"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 16128.309985825315,
            "unit": "iter/sec",
            "range": "stddev: 0.000003837856495981389",
            "extra": "mean: 62.00277653882333 usec\nrounds: 6368"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 10345.832550684006,
            "unit": "iter/sec",
            "range": "stddev: 0.000004555163746003346",
            "extra": "mean: 96.6572767441404 usec\nrounds: 7740"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 12503.192341362259,
            "unit": "iter/sec",
            "range": "stddev: 0.000008648034265208947",
            "extra": "mean: 79.97957423176352 usec\nrounds: 6931"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 91383.98186309938,
            "unit": "iter/sec",
            "range": "stddev: 0.0000019968801449693787",
            "extra": "mean: 10.94283680369806 usec\nrounds: 27519"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 26479.401520330335,
            "unit": "iter/sec",
            "range": "stddev: 0.00001849489839885881",
            "extra": "mean: 37.765203991949015 usec\nrounds: 14128"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 6074.997892781905,
            "unit": "iter/sec",
            "range": "stddev: 0.000006099995882060422",
            "extra": "mean: 164.60911059543972 usec\nrounds: 3879"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2137.7612529704916,
            "unit": "iter/sec",
            "range": "stddev: 0.00001535360028219515",
            "extra": "mean: 467.7790836607531 usec\nrounds: 1530"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 91254.68029507935,
            "unit": "iter/sec",
            "range": "stddev: 0.000001229581064826734",
            "extra": "mean: 10.958342046308415 usec\nrounds: 33551"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 18042.838953765237,
            "unit": "iter/sec",
            "range": "stddev: 0.000003317127469890227",
            "extra": "mean: 55.42365048884487 usec\nrounds: 11147"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1343.9140542499908,
            "unit": "iter/sec",
            "range": "stddev: 0.000009571048466040252",
            "extra": "mean: 744.0952022471989 usec\nrounds: 1068"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 183.28009573636592,
            "unit": "iter/sec",
            "range": "stddev: 0.00004463348545389628",
            "extra": "mean: 5.456129843135949 msec\nrounds: 153"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.3832395316434526,
            "unit": "iter/sec",
            "range": "stddev: 0.030500838349793537",
            "extra": "mean: 2.6093341564000014 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 72219.97515495308,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012206687815573675",
            "extra": "mean: 13.846584658253192 usec\nrounds: 26164"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 6613.0054128941065,
            "unit": "iter/sec",
            "range": "stddev: 0.000006414297986655562",
            "extra": "mean: 151.21717548426463 usec\nrounds: 5009"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 159.85495100262392,
            "unit": "iter/sec",
            "range": "stddev: 0.00004707301475623125",
            "extra": "mean: 6.255671117647057 msec\nrounds: 153"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 72827.14321246743,
            "unit": "iter/sec",
            "range": "stddev: 0.000001355672307760649",
            "extra": "mean: 13.731144129635554 usec\nrounds: 29751"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 15205.969414080939,
            "unit": "iter/sec",
            "range": "stddev: 0.0000033407763034044006",
            "extra": "mean: 65.7636466816766 usec\nrounds: 8890"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 2764.0905118489827,
            "unit": "iter/sec",
            "range": "stddev: 0.000008013913698086639",
            "extra": "mean: 361.7826535394712 usec\nrounds: 2006"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 792.1692795759209,
            "unit": "iter/sec",
            "range": "stddev: 0.000030489450410522622",
            "extra": "mean: 1.2623564505497347 msec\nrounds: 637"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6222.90302698883,
            "unit": "iter/sec",
            "range": "stddev: 0.00000561051650151734",
            "extra": "mean: 160.69670307619836 usec\nrounds: 4193"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1352.173586898503,
            "unit": "iter/sec",
            "range": "stddev: 0.000018707634422106984",
            "extra": "mean: 739.5500176081033 usec\nrounds: 1079"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 161.75096297158677,
            "unit": "iter/sec",
            "range": "stddev: 0.000055959255243735345",
            "extra": "mean: 6.182343410070828 msec\nrounds: 139"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 2731.8558424202733,
            "unit": "iter/sec",
            "range": "stddev: 0.000006468227036289005",
            "extra": "mean: 366.0515260256395 usec\nrounds: 1998"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 53.74265496979094,
            "unit": "iter/sec",
            "range": "stddev: 0.00023012718218377357",
            "extra": "mean: 18.607193867926803 msec\nrounds: 53"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1255.087279951525,
            "unit": "iter/sec",
            "range": "stddev: 0.000022211978184070532",
            "extra": "mean: 796.7573378949572 usec\nrounds: 1169"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 404.316140179403,
            "unit": "iter/sec",
            "range": "stddev: 0.00010476930445606356",
            "extra": "mean: 2.473312095718663 msec\nrounds: 397"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1484.7909130911376,
            "unit": "iter/sec",
            "range": "stddev: 0.00002109934848543538",
            "extra": "mean: 673.4955010723583 usec\nrounds: 1399"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 489.39517088360424,
            "unit": "iter/sec",
            "range": "stddev: 0.000032712124375164296",
            "extra": "mean: 2.043338511482444 msec\nrounds: 479"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 351.5149987200929,
            "unit": "iter/sec",
            "range": "stddev: 0.00004697067890949641",
            "extra": "mean: 2.844828822784566 msec\nrounds: 316"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1610.1311647040711,
            "unit": "iter/sec",
            "range": "stddev: 0.00002357536133999644",
            "extra": "mean: 621.0674148300159 usec\nrounds: 998"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1254.1556033813958,
            "unit": "iter/sec",
            "range": "stddev: 0.000039444259987793376",
            "extra": "mean: 797.3492262872697 usec\nrounds: 738"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 844.9867077766218,
            "unit": "iter/sec",
            "range": "stddev: 0.0014045214774744369",
            "extra": "mean: 1.1834505688630987 msec\nrounds: 835"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 62.75555483020985,
            "unit": "iter/sec",
            "range": "stddev: 0.010851384761987085",
            "extra": "mean: 15.934844376813807 msec\nrounds: 69"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 5.847122145413156,
            "unit": "iter/sec",
            "range": "stddev: 0.04405458354290553",
            "extra": "mean: 171.0243048000052 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 270.3617113172878,
            "unit": "iter/sec",
            "range": "stddev: 0.00006468966078405036",
            "extra": "mean: 3.698748595456374 msec\nrounds: 220"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 65.38422298091581,
            "unit": "iter/sec",
            "range": "stddev: 0.009679756855034721",
            "extra": "mean: 15.294209434772633 msec\nrounds: 23"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 31.41396126691258,
            "unit": "iter/sec",
            "range": "stddev: 0.014967195897449914",
            "extra": "mean: 31.8329799767491 msec\nrounds: 43"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 22.570557762430795,
            "unit": "iter/sec",
            "range": "stddev: 0.017405191224066363",
            "extra": "mean: 44.305506781251225 msec\nrounds: 32"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 884.0164751036447,
            "unit": "iter/sec",
            "range": "stddev: 0.0012683127595745683",
            "extra": "mean: 1.13120063727631 msec\nrounds: 896"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 61.33495469166089,
            "unit": "iter/sec",
            "range": "stddev: 0.011477707144173836",
            "extra": "mean: 16.30391682894583 msec\nrounds: 76"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 5.66947794699414,
            "unit": "iter/sec",
            "range": "stddev: 0.04393190506023048",
            "extra": "mean: 176.38308312499618 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 288.67162182101714,
            "unit": "iter/sec",
            "range": "stddev: 0.00005901200183640066",
            "extra": "mean: 3.464143768936257 msec\nrounds: 264"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 63.65775056247499,
            "unit": "iter/sec",
            "range": "stddev: 0.011200244174332376",
            "extra": "mean: 15.709006227271258 msec\nrounds: 22"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 31.120618088420304,
            "unit": "iter/sec",
            "range": "stddev: 0.015432111851618845",
            "extra": "mean: 32.13303788372028 msec\nrounds: 43"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 22.156243437229563,
            "unit": "iter/sec",
            "range": "stddev: 0.017894151548059914",
            "extra": "mean: 45.134004906250524 msec\nrounds: 32"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 15798.553863599274,
            "unit": "iter/sec",
            "range": "stddev: 0.0000036869949649853343",
            "extra": "mean: 63.29693265812476 usec\nrounds: 9578"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 960.1714202778082,
            "unit": "iter/sec",
            "range": "stddev: 0.000024342535860466268",
            "extra": "mean: 1.0414806969683268 msec\nrounds: 528"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 60.14284602290044,
            "unit": "iter/sec",
            "range": "stddev: 0.0014615557198297115",
            "extra": "mean: 16.627081459018957 msec\nrounds: 61"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1067.9255523393888,
            "unit": "iter/sec",
            "range": "stddev: 0.000021201993244222325",
            "extra": "mean: 936.3948618041851 usec\nrounds: 521"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 955.7600881072915,
            "unit": "iter/sec",
            "range": "stddev: 0.00002987599307001526",
            "extra": "mean: 1.0462876745358949 msec\nrounds: 593"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 889.214384590497,
            "unit": "iter/sec",
            "range": "stddev: 0.000037086709794851736",
            "extra": "mean: 1.124588195298395 msec\nrounds: 553"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 888.1365217767011,
            "unit": "iter/sec",
            "range": "stddev: 0.000027589806528626003",
            "extra": "mean: 1.1259530212759612 msec\nrounds: 517"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 124.0571817280884,
            "unit": "iter/sec",
            "range": "stddev: 0.00034311340179279574",
            "extra": "mean: 8.060798948277133 msec\nrounds: 116"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 128.24724901031266,
            "unit": "iter/sec",
            "range": "stddev: 0.0005791764755134816",
            "extra": "mean: 7.797438211868292 msec\nrounds: 118"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 91.09417097949225,
            "unit": "iter/sec",
            "range": "stddev: 0.0009208961488143301",
            "extra": "mean: 10.977650811764091 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 57.76961096694347,
            "unit": "iter/sec",
            "range": "stddev: 0.011970268924328219",
            "extra": "mean: 17.310139072465162 msec\nrounds: 69"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 15.728078745032306,
            "unit": "iter/sec",
            "range": "stddev: 0.023575837050641178",
            "extra": "mean: 63.58055654546165 msec\nrounds: 11"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 5.526216396836168,
            "unit": "iter/sec",
            "range": "stddev: 0.030145443156131293",
            "extra": "mean: 180.95563549999838 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.068870728718681,
            "unit": "iter/sec",
            "range": "stddev: 0.015090469198765675",
            "extra": "mean: 483.3554779999872 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 38.71732085031147,
            "unit": "iter/sec",
            "range": "stddev: 0.01523690831536273",
            "extra": "mean: 25.828233411763957 msec\nrounds: 51"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 13.257425351919178,
            "unit": "iter/sec",
            "range": "stddev: 0.021883101448795142",
            "extra": "mean: 75.42942716665853 msec\nrounds: 12"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 5.6423116400707976,
            "unit": "iter/sec",
            "range": "stddev: 0.021873140569504894",
            "extra": "mean: 177.2323231666538 msec\nrounds: 6"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 2.9231462619950364,
            "unit": "iter/sec",
            "range": "stddev: 0.037160387686549244",
            "extra": "mean: 342.0971482000027 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 38.968240570717015,
            "unit": "iter/sec",
            "range": "stddev: 0.015207789312034009",
            "extra": "mean: 25.66192328301981 msec\nrounds: 53"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 449008.32429686753,
            "unit": "iter/sec",
            "range": "stddev: 4.881088457594783e-7",
            "extra": "mean: 2.227130202020124 usec\nrounds: 76197"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1310789.7126978498,
            "unit": "iter/sec",
            "range": "stddev: 3.8645626429238157e-7",
            "extra": "mean: 762.8988771523186 nsec\nrounds: 104734"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 121.64748197253951,
            "unit": "iter/sec",
            "range": "stddev: 0.00007471944375903646",
            "extra": "mean: 8.220474306453283 msec\nrounds: 124"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3363201.7089772345,
            "unit": "iter/sec",
            "range": "stddev: 3.611802799377364e-8",
            "extra": "mean: 297.33571951118705 nsec\nrounds: 163881"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4365711.757668499,
            "unit": "iter/sec",
            "range": "stddev: 3.2090326448127674e-8",
            "extra": "mean: 229.0577242630531 nsec\nrounds: 197278"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4128023.0439215857,
            "unit": "iter/sec",
            "range": "stddev: 2.9459484132386486e-8",
            "extra": "mean: 242.24670971071149 nsec\nrounds: 194175"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 3946428.04405829,
            "unit": "iter/sec",
            "range": "stddev: 3.294466477389373e-8",
            "extra": "mean: 253.3936990199509 nsec\nrounds: 196890"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3449739.5242464966,
            "unit": "iter/sec",
            "range": "stddev: 3.6931848763069166e-8",
            "extra": "mean: 289.8769582374261 nsec\nrounds: 189754"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 29268.997124582645,
            "unit": "iter/sec",
            "range": "stddev: 0.000003737016251791108",
            "extra": "mean: 34.165844348664514 usec\nrounds: 5114"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 29.55997398143005,
            "unit": "iter/sec",
            "range": "stddev: 0.00016082267528884985",
            "extra": "mean: 33.82952909999896 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 6464568.416428335,
            "unit": "iter/sec",
            "range": "stddev: 1.1585586216954899e-8",
            "extra": "mean: 154.68936757768876 nsec\nrounds: 66016"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 31886.442021649942,
            "unit": "iter/sec",
            "range": "stddev: 0.000004047328313730141",
            "extra": "mean: 31.361291401562763 usec\nrounds: 11153"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 31926.14750355929,
            "unit": "iter/sec",
            "range": "stddev: 0.000003893102064987094",
            "extra": "mean: 31.32228841229638 usec\nrounds: 18529"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 31518.885296989563,
            "unit": "iter/sec",
            "range": "stddev: 0.0000036497065108700334",
            "extra": "mean: 31.727010348792763 usec\nrounds: 10919"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 215149.8245696741,
            "unit": "iter/sec",
            "range": "stddev: 8.109944837067026e-7",
            "extra": "mean: 4.647923845627679 usec\nrounds: 74047"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 216807.40818779173,
            "unit": "iter/sec",
            "range": "stddev: 7.788121073479865e-7",
            "extra": "mean: 4.612388517341767 usec\nrounds: 113161"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 214051.0982707674,
            "unit": "iter/sec",
            "range": "stddev: 8.244267926204007e-7",
            "extra": "mean: 4.671781682404795 usec\nrounds: 107678"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 181905.02958602473,
            "unit": "iter/sec",
            "range": "stddev: 9.329360423903625e-7",
            "extra": "mean: 5.497374109312848 usec\nrounds: 21328"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 218.224921832038,
            "unit": "iter/sec",
            "range": "stddev: 0.0006150836563966701",
            "extra": "mean: 4.5824280361968635 msec\nrounds: 221"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 31244.55320149837,
            "unit": "iter/sec",
            "range": "stddev: 0.000006609784168094174",
            "extra": "mean: 32.00557849398351 usec\nrounds: 9523"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 30227.995834413712,
            "unit": "iter/sec",
            "range": "stddev: 0.000013299575612891274",
            "extra": "mean: 33.081915370040136 usec\nrounds: 15101"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 31760.33074910272,
            "unit": "iter/sec",
            "range": "stddev: 0.000004010094606466305",
            "extra": "mean: 31.48581820194841 usec\nrounds: 13449"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 31362.571220771344,
            "unit": "iter/sec",
            "range": "stddev: 0.0000041944688609282265",
            "extra": "mean: 31.885140824732595 usec\nrounds: 14550"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.3519935574414492,
            "unit": "iter/sec",
            "range": "stddev: 0.001420533903277045",
            "extra": "mean: 298.32992900001045 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 26024.94643971145,
            "unit": "iter/sec",
            "range": "stddev: 0.000003845962268508003",
            "extra": "mean: 38.4246708179234 usec\nrounds: 9396"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 25903.135739871086,
            "unit": "iter/sec",
            "range": "stddev: 0.000004257219478272807",
            "extra": "mean: 38.60536461849143 usec\nrounds: 13148"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 26020.00346192243,
            "unit": "iter/sec",
            "range": "stddev: 0.0000038320340542541895",
            "extra": "mean: 38.43197029021906 usec\nrounds: 13228"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 167851.75630816427,
            "unit": "iter/sec",
            "range": "stddev: 0.000004177086976767075",
            "extra": "mean: 5.957637989584505 usec\nrounds: 29966"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 19059.75352273752,
            "unit": "iter/sec",
            "range": "stddev: 0.000005012972020253635",
            "extra": "mean: 52.46657564627162 usec\nrounds: 12261"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1936.5853192486954,
            "unit": "iter/sec",
            "range": "stddev: 0.000012799654067072544",
            "extra": "mean: 516.3728083965613 usec\nrounds: 1858"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 207306.74061496538,
            "unit": "iter/sec",
            "range": "stddev: 0.000001027900883574769",
            "extra": "mean: 4.8237698254940895 usec\nrounds: 24186"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 3224.9232653242875,
            "unit": "iter/sec",
            "range": "stddev: 0.000028822115776298114",
            "extra": "mean: 310.0848974462167 usec\nrounds: 2272"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 1647.984014254272,
            "unit": "iter/sec",
            "range": "stddev: 0.00008267147515508416",
            "extra": "mean: 606.8020025379368 usec\nrounds: 1182"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 607.2621384759882,
            "unit": "iter/sec",
            "range": "stddev: 0.000041629129922012836",
            "extra": "mean: 1.6467353003591563 msec\nrounds: 556"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 48275.07708051732,
            "unit": "iter/sec",
            "range": "stddev: 0.000002187289372651957",
            "extra": "mean: 20.71462254388769 usec\nrounds: 14709"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 29.23550254055256,
            "unit": "iter/sec",
            "range": "stddev: 0.0002529960576355671",
            "extra": "mean: 34.204987535716214 msec\nrounds: 28"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 21809.63991038843,
            "unit": "iter/sec",
            "range": "stddev: 0.0000037807871369713005",
            "extra": "mean: 45.85128429945683 usec\nrounds: 8681"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 8298.931061045116,
            "unit": "iter/sec",
            "range": "stddev: 0.00000675869153238327",
            "extra": "mean: 120.49744631497953 usec\nrounds: 4694"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 12200.920164674066,
            "unit": "iter/sec",
            "range": "stddev: 0.0000046828955146482175",
            "extra": "mean: 81.96103134051725 usec\nrounds: 8647"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3605.372208099367,
            "unit": "iter/sec",
            "range": "stddev: 0.00010878356925495827",
            "extra": "mean: 277.36387320940906 usec\nrounds: 1885"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 1667597.3463155096,
            "unit": "iter/sec",
            "range": "stddev: 2.1227474509760322e-7",
            "extra": "mean: 599.6651423135569 nsec\nrounds: 172088"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1580911.9189532076,
            "unit": "iter/sec",
            "range": "stddev: 2.356785262078552e-7",
            "extra": "mean: 632.5463095136538 nsec\nrounds: 168011"
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
          "id": "d8488c6100d2756808dde4774917398446dcc03e",
          "message": "Fix Mermaid diagram parse error in architecture section\n\nQuote the Vector Index node label to prevent parentheses in\n\"HNSW (optional)\" from being parsed as a Mermaid shape delimiter.",
          "timestamp": "2026-03-12T23:54:29+09:00",
          "tree_id": "e978561b315be5889c6ebd795e3fbeecedf4a79c",
          "url": "https://github.com/cognica-io/uqa/commit/d8488c6100d2756808dde4774917398446dcc03e"
        },
        "date": 1773327593565,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 18035.51011431035,
            "unit": "iter/sec",
            "range": "stddev: 0.0000042443383149122876",
            "extra": "mean: 55.4461722270082 usec\nrounds: 3327"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 5907.83127611944,
            "unit": "iter/sec",
            "range": "stddev: 0.0000069830638515433746",
            "extra": "mean: 169.26685161815422 usec\nrounds: 3801"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 9160.705852641891,
            "unit": "iter/sec",
            "range": "stddev: 0.0000055541570908661286",
            "extra": "mean: 109.1618938634086 usec\nrounds: 5785"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 3816.4123914090133,
            "unit": "iter/sec",
            "range": "stddev: 0.000010428533446257313",
            "extra": "mean: 262.0261904219428 usec\nrounds: 2631"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 8739.458179952146,
            "unit": "iter/sec",
            "range": "stddev: 0.000005652615974481028",
            "extra": "mean: 114.4235694489559 usec\nrounds: 5990"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 4622.500217920048,
            "unit": "iter/sec",
            "range": "stddev: 0.00007121489644772374",
            "extra": "mean: 216.3331428570408 usec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 1551.474360780199,
            "unit": "iter/sec",
            "range": "stddev: 0.0000306992971325219",
            "extra": "mean: 644.548195754343 usec\nrounds: 1272"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4033.5536809048763,
            "unit": "iter/sec",
            "range": "stddev: 0.000025593192251237652",
            "extra": "mean: 247.9203400054075 usec\nrounds: 50"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 5048.383507629532,
            "unit": "iter/sec",
            "range": "stddev: 0.000016740745902531258",
            "extra": "mean: 198.08320791966733 usec\nrounds: 202"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 3669.0067551073666,
            "unit": "iter/sec",
            "range": "stddev: 0.0002771835554629528",
            "extra": "mean: 272.55332757509103 usec\nrounds: 3184"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 9253.097604976878,
            "unit": "iter/sec",
            "range": "stddev: 0.000006899484948126387",
            "extra": "mean: 108.07191739360225 usec\nrounds: 5387"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 6879.432033401856,
            "unit": "iter/sec",
            "range": "stddev: 0.000014522949048209106",
            "extra": "mean: 145.3608372238694 usec\nrounds: 4798"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 5977.485277706032,
            "unit": "iter/sec",
            "range": "stddev: 0.000015549470111751353",
            "extra": "mean: 167.29443127692116 usec\nrounds: 3485"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 5358.733242823095,
            "unit": "iter/sec",
            "range": "stddev: 0.000014612332224933234",
            "extra": "mean: 186.61126700779357 usec\nrounds: 3910"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 3324.5507290058895,
            "unit": "iter/sec",
            "range": "stddev: 0.000020249978924046678",
            "extra": "mean: 300.79252251296555 usec\nrounds: 955"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1280.713646748849,
            "unit": "iter/sec",
            "range": "stddev: 0.000028884579960412306",
            "extra": "mean: 780.8146673056436 usec\nrounds: 1043"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 9033.119391180968,
            "unit": "iter/sec",
            "range": "stddev: 0.00000681872729449978",
            "extra": "mean: 110.703728877568 usec\nrounds: 5835"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 7985.75481457071,
            "unit": "iter/sec",
            "range": "stddev: 0.000007927760350734532",
            "extra": "mean: 125.22297806782302 usec\nrounds: 6201"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 3495.2774147518253,
            "unit": "iter/sec",
            "range": "stddev: 0.00001542800755851049",
            "extra": "mean: 286.1003237624281 usec\nrounds: 2020"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 5015.878387652638,
            "unit": "iter/sec",
            "range": "stddev: 0.00001721665547802752",
            "extra": "mean: 199.36687509443112 usec\nrounds: 3987"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 3512.4353488265997,
            "unit": "iter/sec",
            "range": "stddev: 0.000015131640313661944",
            "extra": "mean: 284.7027491435736 usec\nrounds: 2627"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1798.5171955091926,
            "unit": "iter/sec",
            "range": "stddev: 0.00001898230940484719",
            "extra": "mean: 556.0135885811657 usec\nrounds: 1191"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1503.4211324109685,
            "unit": "iter/sec",
            "range": "stddev: 0.000018693425053634944",
            "extra": "mean: 665.1496233768812 usec\nrounds: 1309"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1626.9175040125933,
            "unit": "iter/sec",
            "range": "stddev: 0.00045148988543519897",
            "extra": "mean: 614.659315874113 usec\nrounds: 6835"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 1932.1997377198493,
            "unit": "iter/sec",
            "range": "stddev: 0.000022840273214938857",
            "extra": "mean: 517.5448378748256 usec\nrounds: 1468"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 1426.5950984193935,
            "unit": "iter/sec",
            "range": "stddev: 0.0000185298639851012",
            "extra": "mean: 700.9697433476096 usec\nrounds: 1165"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 98.05822393933484,
            "unit": "iter/sec",
            "range": "stddev: 0.0026558989004055126",
            "extra": "mean: 10.198022764706248 msec\nrounds: 102"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 101.0166850492144,
            "unit": "iter/sec",
            "range": "stddev: 0.002206092017335464",
            "extra": "mean: 9.8993547403858 msec\nrounds: 104"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 134.5859209651956,
            "unit": "iter/sec",
            "range": "stddev: 0.0025952961041914744",
            "extra": "mean: 7.430197696968641 msec\nrounds: 132"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 170.7528681786024,
            "unit": "iter/sec",
            "range": "stddev: 0.002161047753592936",
            "extra": "mean: 5.856417000000433 msec\nrounds: 170"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 160.35730096012864,
            "unit": "iter/sec",
            "range": "stddev: 0.0018120532333891388",
            "extra": "mean: 6.236074029760833 msec\nrounds: 168"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 113.38473522196219,
            "unit": "iter/sec",
            "range": "stddev: 0.0023568398374536454",
            "extra": "mean: 8.819529348835166 msec\nrounds: 43"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 272.80702123666043,
            "unit": "iter/sec",
            "range": "stddev: 0.0009406184998744645",
            "extra": "mean: 3.665594805686833 msec\nrounds: 211"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 75.37318803006353,
            "unit": "iter/sec",
            "range": "stddev: 0.002567960741724553",
            "extra": "mean: 13.26731728000065 msec\nrounds: 75"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.11102704771471245,
            "unit": "iter/sec",
            "range": "stddev: 0.03843679284539853",
            "extra": "mean: 9.0068142906 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 14.260806849412694,
            "unit": "iter/sec",
            "range": "stddev: 0.00026366751887077277",
            "extra": "mean: 70.12225960000175 msec\nrounds: 15"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 58.5087711794463,
            "unit": "iter/sec",
            "range": "stddev: 0.0035621977329629725",
            "extra": "mean: 17.091454492062425 msec\nrounds: 63"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 74.62877430326449,
            "unit": "iter/sec",
            "range": "stddev: 0.0029776677670002166",
            "extra": "mean: 13.399657294870737 msec\nrounds: 78"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 172.79096940781872,
            "unit": "iter/sec",
            "range": "stddev: 0.0008642849297411312",
            "extra": "mean: 5.787339485548083 msec\nrounds: 173"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 147.5005179563447,
            "unit": "iter/sec",
            "range": "stddev: 0.0010159695769556064",
            "extra": "mean: 6.779637209789101 msec\nrounds: 143"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 345.8933466013245,
            "unit": "iter/sec",
            "range": "stddev: 0.000030383829637155877",
            "extra": "mean: 2.8910645718565866 msec\nrounds: 334"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 1938.9337976868933,
            "unit": "iter/sec",
            "range": "stddev: 0.00001660983247986168",
            "extra": "mean: 515.7473665129663 usec\nrounds: 1517"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 476.59164017568816,
            "unit": "iter/sec",
            "range": "stddev: 0.000881562006857239",
            "extra": "mean: 2.0982323559669775 msec\nrounds: 486"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 239.53934373066335,
            "unit": "iter/sec",
            "range": "stddev: 0.001697551177793553",
            "extra": "mean: 4.174679551282375 msec\nrounds: 234"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 224.8904757178003,
            "unit": "iter/sec",
            "range": "stddev: 0.001680942834187973",
            "extra": "mean: 4.446608940677557 msec\nrounds: 236"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1621.0913042618047,
            "unit": "iter/sec",
            "range": "stddev: 0.000014737767860061069",
            "extra": "mean: 616.8684005466116 usec\nrounds: 1463"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 138.7534740631661,
            "unit": "iter/sec",
            "range": "stddev: 0.0025788428503044614",
            "extra": "mean: 7.207026755559001 msec\nrounds: 45"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 234.48477599129356,
            "unit": "iter/sec",
            "range": "stddev: 0.0017352320695135748",
            "extra": "mean: 4.264669191304471 msec\nrounds: 230"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 77.7707618338266,
            "unit": "iter/sec",
            "range": "stddev: 0.0025489274486744976",
            "extra": "mean: 12.858302740259996 msec\nrounds: 77"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 62.8338441294571,
            "unit": "iter/sec",
            "range": "stddev: 0.0026648356396542297",
            "extra": "mean: 15.914989984373573 msec\nrounds: 64"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 88.22854375066554,
            "unit": "iter/sec",
            "range": "stddev: 0.002308329532798461",
            "extra": "mean: 11.33420044680786 msec\nrounds: 94"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 63.37896922361606,
            "unit": "iter/sec",
            "range": "stddev: 0.0024218376165968643",
            "extra": "mean: 15.778104507691856 msec\nrounds: 65"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 106.43450657001907,
            "unit": "iter/sec",
            "range": "stddev: 0.0019760534430139634",
            "extra": "mean: 9.39544920370481 msec\nrounds: 108"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 99.76260303311196,
            "unit": "iter/sec",
            "range": "stddev: 0.002505116628645099",
            "extra": "mean: 10.02379618811763 msec\nrounds: 101"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 90.35969348608042,
            "unit": "iter/sec",
            "range": "stddev: 0.0027905973069849628",
            "extra": "mean: 11.06688127659537 msec\nrounds: 94"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 174.09482567456607,
            "unit": "iter/sec",
            "range": "stddev: 0.0016730845213510294",
            "extra": "mean: 5.743996101695126 msec\nrounds: 177"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 158.4341927604515,
            "unit": "iter/sec",
            "range": "stddev: 0.002494801403516855",
            "extra": "mean: 6.311768833334952 msec\nrounds: 168"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 169.53923160750088,
            "unit": "iter/sec",
            "range": "stddev: 0.0014275705562743432",
            "extra": "mean: 5.898339815029321 msec\nrounds: 173"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 146.65364650805344,
            "unit": "iter/sec",
            "range": "stddev: 0.0012409203965972277",
            "extra": "mean: 6.818787147887832 msec\nrounds: 142"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 40.24802786801641,
            "unit": "iter/sec",
            "range": "stddev: 0.00029263417282720714",
            "extra": "mean: 24.84593787499989 msec\nrounds: 40"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 235.29100428899912,
            "unit": "iter/sec",
            "range": "stddev: 0.0017431774643085788",
            "extra": "mean: 4.250056235774053 msec\nrounds: 246"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 230.51527563639854,
            "unit": "iter/sec",
            "range": "stddev: 0.0018408219792042497",
            "extra": "mean: 4.338107300000986 msec\nrounds: 230"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 81.09937913819832,
            "unit": "iter/sec",
            "range": "stddev: 0.0030871026619551053",
            "extra": "mean: 12.330550623524982 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 88.6482616238862,
            "unit": "iter/sec",
            "range": "stddev: 0.002507856871292731",
            "extra": "mean: 11.280537053763847 msec\nrounds: 93"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 640093.6792388954,
            "unit": "iter/sec",
            "range": "stddev: 3.568495857916381e-7",
            "extra": "mean: 1.5622713243927855 usec\nrounds: 87482"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 262833.7048461211,
            "unit": "iter/sec",
            "range": "stddev: 6.031209034373841e-7",
            "extra": "mean: 3.8046870761322684 usec\nrounds: 86267"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 77630.45509856979,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011296225808427617",
            "extra": "mean: 12.881542414381947 usec\nrounds: 36509"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 773287.3341423078,
            "unit": "iter/sec",
            "range": "stddev: 3.198913963720604e-7",
            "extra": "mean: 1.293180368858816 usec\nrounds: 181456"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2094994.8528078024,
            "unit": "iter/sec",
            "range": "stddev: 6.402213944434966e-8",
            "extra": "mean: 477.3281417182276 nsec\nrounds: 178891"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1690611.494130966,
            "unit": "iter/sec",
            "range": "stddev: 7.462034132484737e-8",
            "extra": "mean: 591.5019526789833 nsec\nrounds: 185529"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2411510.2123725875,
            "unit": "iter/sec",
            "range": "stddev: 5.7965474769268654e-8",
            "extra": "mean: 414.6779038584873 nsec\nrounds: 197668"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 178179.56635089152,
            "unit": "iter/sec",
            "range": "stddev: 6.916323774181058e-7",
            "extra": "mean: 5.6123158254335745 usec\nrounds: 103972"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1617.5145669649207,
            "unit": "iter/sec",
            "range": "stddev: 0.000016739649915850385",
            "extra": "mean: 618.2324539286125 usec\nrounds: 1476"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1614.4597315556068,
            "unit": "iter/sec",
            "range": "stddev: 0.000018374077827594904",
            "extra": "mean: 619.4022560330158 usec\nrounds: 1492"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 444155.63303668785,
            "unit": "iter/sec",
            "range": "stddev: 5.48861284664238e-7",
            "extra": "mean: 2.251463058484724 usec\nrounds: 81480"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 194154.01986441584,
            "unit": "iter/sec",
            "range": "stddev: 7.072130567952646e-7",
            "extra": "mean: 5.150550066891909 usec\nrounds: 72433"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 117458.21883438558,
            "unit": "iter/sec",
            "range": "stddev: 9.946635635628494e-7",
            "extra": "mean: 8.513665624454816 usec\nrounds: 54693"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 340522.1212789054,
            "unit": "iter/sec",
            "range": "stddev: 5.970668829883857e-7",
            "extra": "mean: 2.936666775844932 usec\nrounds: 112906"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 102203.22852715536,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010028818926706721",
            "extra": "mean: 9.784426719301733 usec\nrounds: 54994"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 16027.886543809424,
            "unit": "iter/sec",
            "range": "stddev: 0.0000033949262869746386",
            "extra": "mean: 62.39125771614835 usec\nrounds: 6026"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 10412.789968458217,
            "unit": "iter/sec",
            "range": "stddev: 0.000004813452122212148",
            "extra": "mean: 96.03574095215005 usec\nrounds: 8041"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 12546.720440860616,
            "unit": "iter/sec",
            "range": "stddev: 0.0000040458348495207575",
            "extra": "mean: 79.70210261028238 usec\nrounds: 8391"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 91769.67434777021,
            "unit": "iter/sec",
            "range": "stddev: 0.000001250369254630771",
            "extra": "mean: 10.89684590369583 usec\nrounds: 29514"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 26662.70334668916,
            "unit": "iter/sec",
            "range": "stddev: 0.000002451145155058879",
            "extra": "mean: 37.505574247188065 usec\nrounds: 14445"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 6099.143611437062,
            "unit": "iter/sec",
            "range": "stddev: 0.000004529135582902425",
            "extra": "mean: 163.95744447217288 usec\nrounds: 4052"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2121.9921769404277,
            "unit": "iter/sec",
            "range": "stddev: 0.0000097376900722731",
            "extra": "mean: 471.2552717521511 usec\nrounds: 1586"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 91393.46797405822,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011838790479550385",
            "extra": "mean: 10.941701000818211 usec\nrounds: 36164"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 18213.67301979442,
            "unit": "iter/sec",
            "range": "stddev: 0.000003020049276145089",
            "extra": "mean: 54.90380764567427 usec\nrounds: 10777"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1347.1205863602793,
            "unit": "iter/sec",
            "range": "stddev: 0.000010048989502499397",
            "extra": "mean: 742.3240429439596 usec\nrounds: 652"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 182.45205572782604,
            "unit": "iter/sec",
            "range": "stddev: 0.00003521266923348017",
            "extra": "mean: 5.480891930819109 msec\nrounds: 159"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.3829849158955119,
            "unit": "iter/sec",
            "range": "stddev: 0.022636369012999945",
            "extra": "mean: 2.61106889199998 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 72519.05705402094,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013570808909188963",
            "extra": "mean: 13.789478802173052 usec\nrounds: 26984"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 6607.653874595843,
            "unit": "iter/sec",
            "range": "stddev: 0.0000049874221726636065",
            "extra": "mean: 151.3396462615356 usec\nrounds: 4721"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 159.82021984330171,
            "unit": "iter/sec",
            "range": "stddev: 0.000047880708111673426",
            "extra": "mean: 6.257030562093244 msec\nrounds: 153"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 71354.03744780342,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012940261596132592",
            "extra": "mean: 14.014623919936069 usec\nrounds: 30903"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 14897.511465172242,
            "unit": "iter/sec",
            "range": "stddev: 0.0000030246003875959093",
            "extra": "mean: 67.12530494356885 usec\nrounds: 9123"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 2720.7308298246967,
            "unit": "iter/sec",
            "range": "stddev: 0.000007044411227116273",
            "extra": "mean: 367.5483032124984 usec\nrounds: 1992"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 782.0632964380275,
            "unit": "iter/sec",
            "range": "stddev: 0.000018587573318689547",
            "extra": "mean: 1.2786688808368627 msec\nrounds: 621"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6072.1244280712,
            "unit": "iter/sec",
            "range": "stddev: 0.000009123229414383506",
            "extra": "mean: 164.68700729797928 usec\nrounds: 3974"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1329.921788681914,
            "unit": "iter/sec",
            "range": "stddev: 0.00001267218242114558",
            "extra": "mean: 751.9239165117374 usec\nrounds: 1078"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 159.28710718651791,
            "unit": "iter/sec",
            "range": "stddev: 0.00003092841268509014",
            "extra": "mean: 6.277972007044146 msec\nrounds: 142"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 2688.4479954445524,
            "unit": "iter/sec",
            "range": "stddev: 0.000008097733564074241",
            "extra": "mean: 371.96181651809985 usec\nrounds: 2022"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 50.82950447384847,
            "unit": "iter/sec",
            "range": "stddev: 0.0002936419446319239",
            "extra": "mean: 19.673612999994816 msec\nrounds: 52"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1232.4468416241032,
            "unit": "iter/sec",
            "range": "stddev: 0.000014852867187839281",
            "extra": "mean: 811.3940222218529 usec\nrounds: 1170"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 400.2907493664977,
            "unit": "iter/sec",
            "range": "stddev: 0.000028588776348310987",
            "extra": "mean: 2.498184136362395 msec\nrounds: 396"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1454.9973615168205,
            "unit": "iter/sec",
            "range": "stddev: 0.000011429639965102015",
            "extra": "mean: 687.2864696864534 usec\nrounds: 1369"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 483.2762715094882,
            "unit": "iter/sec",
            "range": "stddev: 0.000030180322838651936",
            "extra": "mean: 2.0692098059698902 msec\nrounds: 469"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 353.7238369253607,
            "unit": "iter/sec",
            "range": "stddev: 0.00003430378089550576",
            "extra": "mean: 2.8270642111433677 msec\nrounds: 341"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1660.798936445907,
            "unit": "iter/sec",
            "range": "stddev: 0.000013807674326086054",
            "extra": "mean: 602.1198460904544 usec\nrounds: 1202"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1292.7864028978495,
            "unit": "iter/sec",
            "range": "stddev: 0.00001547085351492522",
            "extra": "mean: 773.522987059925 usec\nrounds: 850"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 861.6260187444502,
            "unit": "iter/sec",
            "range": "stddev: 0.0012647278968797573",
            "extra": "mean: 1.1605963355855784 msec\nrounds: 888"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 71.86303237445702,
            "unit": "iter/sec",
            "range": "stddev: 0.007655485823952924",
            "extra": "mean: 13.91536047058654 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 6.034480231031923,
            "unit": "iter/sec",
            "range": "stddev: 0.04457340956012763",
            "extra": "mean: 165.71435512499733 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 267.2624765842394,
            "unit": "iter/sec",
            "range": "stddev: 0.000043881201934301205",
            "extra": "mean: 3.7416401014483847 msec\nrounds: 276"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 73.45569165926547,
            "unit": "iter/sec",
            "range": "stddev: 0.007760560538829097",
            "extra": "mean: 13.613648955054977 msec\nrounds: 89"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 37.00849630660566,
            "unit": "iter/sec",
            "range": "stddev: 0.011160796525910309",
            "extra": "mean: 27.02082223809536 msec\nrounds: 21"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 27.061936694392035,
            "unit": "iter/sec",
            "range": "stddev: 0.012299815147865227",
            "extra": "mean: 36.952270315791075 msec\nrounds: 19"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 910.4203099826459,
            "unit": "iter/sec",
            "range": "stddev: 0.001070672025706747",
            "extra": "mean: 1.098393773771437 msec\nrounds: 915"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 74.15787020909666,
            "unit": "iter/sec",
            "range": "stddev: 0.007569690706471601",
            "extra": "mean: 13.4847454111126 msec\nrounds: 90"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 6.490258144591601,
            "unit": "iter/sec",
            "range": "stddev: 0.041860185469408034",
            "extra": "mean: 154.0770764000058 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 291.25111056464647,
            "unit": "iter/sec",
            "range": "stddev: 0.00004209587586023694",
            "extra": "mean: 3.433463302719454 msec\nrounds: 294"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 75.36138916499594,
            "unit": "iter/sec",
            "range": "stddev: 0.007384769557332288",
            "extra": "mean: 13.26939446154056 msec\nrounds: 91"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 36.84249210107398,
            "unit": "iter/sec",
            "range": "stddev: 0.010961209097298849",
            "extra": "mean: 27.14257214893586 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 26.541027247314204,
            "unit": "iter/sec",
            "range": "stddev: 0.01240987072158854",
            "extra": "mean: 37.67751680000231 msec\nrounds: 20"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 16251.117928052718,
            "unit": "iter/sec",
            "range": "stddev: 0.000003443789143166405",
            "extra": "mean: 61.53422825600187 usec\nrounds: 10405"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 971.1154833603422,
            "unit": "iter/sec",
            "range": "stddev: 0.000012562990870899262",
            "extra": "mean: 1.0297436475214141 msec\nrounds: 888"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 85.61578417311766,
            "unit": "iter/sec",
            "range": "stddev: 0.00027366939201735877",
            "extra": "mean: 11.680089245903188 msec\nrounds: 61"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1078.3893012636054,
            "unit": "iter/sec",
            "range": "stddev: 0.00004831334062796633",
            "extra": "mean: 927.3089030355248 usec\nrounds: 1021"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 970.1842078035781,
            "unit": "iter/sec",
            "range": "stddev: 0.000011386308769813327",
            "extra": "mean: 1.0307320939225784 msec\nrounds: 905"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 908.795502907698,
            "unit": "iter/sec",
            "range": "stddev: 0.000013967949932389299",
            "extra": "mean: 1.1003575576689062 msec\nrounds: 841"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 906.1276381409673,
            "unit": "iter/sec",
            "range": "stddev: 0.0000128983107036045",
            "extra": "mean: 1.1035972835478494 msec\nrounds: 857"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 185.74827129900913,
            "unit": "iter/sec",
            "range": "stddev: 0.0001696129495860542",
            "extra": "mean: 5.383630184047556 msec\nrounds: 163"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 175.13627176955563,
            "unit": "iter/sec",
            "range": "stddev: 0.00022354014799409153",
            "extra": "mean: 5.709839486110567 msec\nrounds: 144"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 107.42333689166811,
            "unit": "iter/sec",
            "range": "stddev: 0.0006153976152764686",
            "extra": "mean: 9.308964224491161 msec\nrounds: 98"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 69.3792618737473,
            "unit": "iter/sec",
            "range": "stddev: 0.008423336092076766",
            "extra": "mean: 14.413528956530943 msec\nrounds: 23"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 18.001334640549278,
            "unit": "iter/sec",
            "range": "stddev: 0.020290768825230864",
            "extra": "mean: 55.551436600007946 msec\nrounds: 25"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 6.3812485283582,
            "unit": "iter/sec",
            "range": "stddev: 0.02587838770114963",
            "extra": "mean: 156.7091448571562 msec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.388520138587383,
            "unit": "iter/sec",
            "range": "stddev: 0.008897051699635892",
            "extra": "mean: 418.6692771999901 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 46.36400327578211,
            "unit": "iter/sec",
            "range": "stddev: 0.01162409112901602",
            "extra": "mean: 21.568456762713208 msec\nrounds: 59"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 14.130438965888771,
            "unit": "iter/sec",
            "range": "stddev: 0.019446938468431957",
            "extra": "mean: 70.7692098181822 msec\nrounds: 22"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 6.256759239573786,
            "unit": "iter/sec",
            "range": "stddev: 0.0014562889999442728",
            "extra": "mean: 159.82715040000812 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 3.0003610130381997,
            "unit": "iter/sec",
            "range": "stddev: 0.03897203743533166",
            "extra": "mean: 333.2932256000049 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 45.42387681371001,
            "unit": "iter/sec",
            "range": "stddev: 0.012358616335584698",
            "extra": "mean: 22.014853644068005 msec\nrounds: 59"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 429880.26535580104,
            "unit": "iter/sec",
            "range": "stddev: 4.5470504567316355e-7",
            "extra": "mean: 2.32622914004281 usec\nrounds: 61805"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1408062.859141541,
            "unit": "iter/sec",
            "range": "stddev: 2.4295310349572653e-7",
            "extra": "mean: 710.1955665599147 nsec\nrounds: 99020"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 123.44126883661048,
            "unit": "iter/sec",
            "range": "stddev: 0.00012861931168749665",
            "extra": "mean: 8.10101847967572 msec\nrounds: 123"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3330023.8562410064,
            "unit": "iter/sec",
            "range": "stddev: 3.626535757945862e-8",
            "extra": "mean: 300.2981489534489 nsec\nrounds: 164177"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4352065.604766765,
            "unit": "iter/sec",
            "range": "stddev: 2.899590271537192e-8",
            "extra": "mean: 229.7759479785213 nsec\nrounds: 194932"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4063790.0065717823,
            "unit": "iter/sec",
            "range": "stddev: 3.0959202510090306e-8",
            "extra": "mean: 246.07570725427345 nsec\nrounds: 188715"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 3911701.2286651414,
            "unit": "iter/sec",
            "range": "stddev: 3.1974213579054835e-8",
            "extra": "mean: 255.6432461334087 nsec\nrounds: 193837"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3437489.0627368037,
            "unit": "iter/sec",
            "range": "stddev: 3.539448417920035e-8",
            "extra": "mean: 290.9100165118304 nsec\nrounds: 189394"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 30303.122075243456,
            "unit": "iter/sec",
            "range": "stddev: 0.0000039470397542840445",
            "extra": "mean: 32.99990006036254 usec\nrounds: 4993"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 30.541151983489655,
            "unit": "iter/sec",
            "range": "stddev: 0.0001648330939946497",
            "extra": "mean: 32.74270729999292 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 6584180.41709588,
            "unit": "iter/sec",
            "range": "stddev: 1.1955957388836175e-8",
            "extra": "mean: 151.8791917371358 nsec\nrounds: 66810"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 32912.740810526615,
            "unit": "iter/sec",
            "range": "stddev: 0.000003492320036293583",
            "extra": "mean: 30.383370554182648 usec\nrounds: 8660"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 32862.99395589493,
            "unit": "iter/sec",
            "range": "stddev: 0.000003628498331475937",
            "extra": "mean: 30.42936384134961 usec\nrounds: 18629"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 32341.846498189105,
            "unit": "iter/sec",
            "range": "stddev: 0.0000042210929308426475",
            "extra": "mean: 30.9196940890803 usec\nrounds: 13821"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 214985.47867592546,
            "unit": "iter/sec",
            "range": "stddev: 7.818424632259237e-7",
            "extra": "mean: 4.651476956299105 usec\nrounds: 74879"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 215440.97090008535,
            "unit": "iter/sec",
            "range": "stddev: 7.952250916074475e-7",
            "extra": "mean: 4.641642654236683 usec\nrounds: 117981"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 214558.5371378112,
            "unit": "iter/sec",
            "range": "stddev: 7.975875621000178e-7",
            "extra": "mean: 4.66073274613025 usec\nrounds: 111396"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 187648.2213394168,
            "unit": "iter/sec",
            "range": "stddev: 8.981518375748773e-7",
            "extra": "mean: 5.329120589910666 usec\nrounds: 23327"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 223.85391175954297,
            "unit": "iter/sec",
            "range": "stddev: 0.00003757506522848568",
            "extra": "mean: 4.467199130628414 msec\nrounds: 222"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 32547.20756734098,
            "unit": "iter/sec",
            "range": "stddev: 0.000003637973395779909",
            "extra": "mean: 30.724602039390792 usec\nrounds: 9315"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 32652.78693396265,
            "unit": "iter/sec",
            "range": "stddev: 0.0000036880695894941785",
            "extra": "mean: 30.62525725667493 usec\nrounds: 15331"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 32651.02676637815,
            "unit": "iter/sec",
            "range": "stddev: 0.000004077229156577455",
            "extra": "mean: 30.626908218081933 usec\nrounds: 14262"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 32151.28001205513,
            "unit": "iter/sec",
            "range": "stddev: 0.0000054774641616488175",
            "extra": "mean: 31.10296074137794 usec\nrounds: 15003"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.3780716038273675,
            "unit": "iter/sec",
            "range": "stddev: 0.0008478754702642475",
            "extra": "mean: 296.0268807999796 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 26863.847907188883,
            "unit": "iter/sec",
            "range": "stddev: 0.000003973806631950652",
            "extra": "mean: 37.22474916679362 usec\nrounds: 10505"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 26746.299583899865,
            "unit": "iter/sec",
            "range": "stddev: 0.0000037686260578532063",
            "extra": "mean: 37.38834962433299 usec\nrounds: 13709"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 26795.413905078585,
            "unit": "iter/sec",
            "range": "stddev: 0.0000041609502364624545",
            "extra": "mean: 37.31981911316802 usec\nrounds: 13666"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 171170.71529805337,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010628099005278886",
            "extra": "mean: 5.84212082223724 usec\nrounds: 32105"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 19122.53811776301,
            "unit": "iter/sec",
            "range": "stddev: 0.0000035117968355033053",
            "extra": "mean: 52.29431333025272 usec\nrounds: 13098"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1925.0400620547955,
            "unit": "iter/sec",
            "range": "stddev: 0.000023371513679128598",
            "extra": "mean: 519.469708558998 usec\nrounds: 1846"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 208315.53305629862,
            "unit": "iter/sec",
            "range": "stddev: 9.397504760697658e-7",
            "extra": "mean: 4.800410153426934 usec\nrounds: 27124"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 3188.307010244095,
            "unit": "iter/sec",
            "range": "stddev: 0.00002648592279230992",
            "extra": "mean: 313.6460813801744 usec\nrounds: 2175"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 1689.1926641966036,
            "unit": "iter/sec",
            "range": "stddev: 0.00004099514167374041",
            "extra": "mean: 591.998782137507 usec\nrounds: 1198"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 614.0915129056993,
            "unit": "iter/sec",
            "range": "stddev: 0.000020105036672814055",
            "extra": "mean: 1.6284217889094346 msec\nrounds: 559"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 49435.2021918276,
            "unit": "iter/sec",
            "range": "stddev: 0.0000018480209344252978",
            "extra": "mean: 20.22850025210002 usec\nrounds: 19832"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 29.74964063742297,
            "unit": "iter/sec",
            "range": "stddev: 0.0002494933529905158",
            "extra": "mean: 33.61385141379052 msec\nrounds: 29"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 22200.971449154942,
            "unit": "iter/sec",
            "range": "stddev: 0.0000036540186818708583",
            "extra": "mean: 45.04307400647839 usec\nrounds: 10391"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 8433.546101056258,
            "unit": "iter/sec",
            "range": "stddev: 0.00000628664833404332",
            "extra": "mean: 118.57408354888285 usec\nrounds: 6188"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 11727.817919467429,
            "unit": "iter/sec",
            "range": "stddev: 0.000004129400086369189",
            "extra": "mean: 85.26735381353967 usec\nrounds: 9033"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3637.5708812182183,
            "unit": "iter/sec",
            "range": "stddev: 0.00010561091786284104",
            "extra": "mean: 274.90873240801324 usec\nrounds: 2089"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 2011912.082643364,
            "unit": "iter/sec",
            "range": "stddev: 6.347058797601151e-8",
            "extra": "mean: 497.03961153518367 nsec\nrounds: 174490"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1865388.4588529316,
            "unit": "iter/sec",
            "range": "stddev: 6.79649205663936e-8",
            "extra": "mean: 536.0813696761702 nsec\nrounds: 183824"
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
          "id": "c83cffaba115cf8f7fe769e76699e72bc8a061b2",
          "message": "Remove License classifier to fix PEP 639 setuptools conflict\n\nThe SPDX license expression in [project].license is incompatible with\nthe License classifier in newer setuptools (75+). Removing the\nredundant classifier fixes the CI build failure.",
          "timestamp": "2026-03-13T11:54:42+09:00",
          "tree_id": "47c750d02557fba75f417eeb8d14df539ce65016",
          "url": "https://github.com/cognica-io/uqa/commit/c83cffaba115cf8f7fe769e76699e72bc8a061b2"
        },
        "date": 1773370803788,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 18041.853269429484,
            "unit": "iter/sec",
            "range": "stddev: 0.000004701272254319547",
            "extra": "mean: 55.426678460711244 usec\nrounds: 3222"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 5824.645059817829,
            "unit": "iter/sec",
            "range": "stddev: 0.000007860938982528788",
            "extra": "mean: 171.68428114163507 usec\nrounds: 3749"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 9044.95957868643,
            "unit": "iter/sec",
            "range": "stddev: 0.000007026544093718391",
            "extra": "mean: 110.55881359120752 usec\nrounds: 5842"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 3789.4363244141855,
            "unit": "iter/sec",
            "range": "stddev: 0.000015987008193331672",
            "extra": "mean: 263.89149055159055 usec\nrounds: 2593"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 8614.011414349918,
            "unit": "iter/sec",
            "range": "stddev: 0.000008780932371504954",
            "extra": "mean: 116.08993207672317 usec\nrounds: 5889"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 4316.434082833445,
            "unit": "iter/sec",
            "range": "stddev: 0.00008497497612584323",
            "extra": "mean: 231.67271428446514 usec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 2532.7793685460542,
            "unit": "iter/sec",
            "range": "stddev: 0.000023690955687876623",
            "extra": "mean: 394.8231782123413 usec\nrounds: 1891"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4655.985653013478,
            "unit": "iter/sec",
            "range": "stddev: 0.00009832778671670038",
            "extra": "mean: 214.77729411661167 usec\nrounds: 51"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 5095.331197032712,
            "unit": "iter/sec",
            "range": "stddev: 0.000016000626739139393",
            "extra": "mean: 196.25809615326955 usec\nrounds: 208"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 3675.3850506673066,
            "unit": "iter/sec",
            "range": "stddev: 0.00022511846883156543",
            "extra": "mean: 272.0803361319759 usec\nrounds: 3216"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 9281.494453039184,
            "unit": "iter/sec",
            "range": "stddev: 0.00000801062949813384",
            "extra": "mean: 107.74127001417908 usec\nrounds: 5696"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 6893.589637878305,
            "unit": "iter/sec",
            "range": "stddev: 0.000014603627075527811",
            "extra": "mean: 145.0623046236007 usec\nrounds: 4888"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 5955.950709926489,
            "unit": "iter/sec",
            "range": "stddev: 0.000015282514266231915",
            "extra": "mean: 167.89930755023698 usec\nrounds: 3788"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 5252.579755343716,
            "unit": "iter/sec",
            "range": "stddev: 0.00001768522254624688",
            "extra": "mean: 190.3826398795086 usec\nrounds: 3982"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 3831.9251145212534,
            "unit": "iter/sec",
            "range": "stddev: 0.00001315767729276686",
            "extra": "mean: 260.965433852153 usec\nrounds: 1028"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1422.3635160468427,
            "unit": "iter/sec",
            "range": "stddev: 0.000027824359670449738",
            "extra": "mean: 703.0551534246938 usec\nrounds: 1095"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 8979.428766645808,
            "unit": "iter/sec",
            "range": "stddev: 0.0000075176750732268606",
            "extra": "mean: 111.36565877269517 usec\nrounds: 5785"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 7917.014187464745,
            "unit": "iter/sec",
            "range": "stddev: 0.0000075542153063573885",
            "extra": "mean: 126.31024478689594 usec\nrounds: 5515"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 4066.118803045121,
            "unit": "iter/sec",
            "range": "stddev: 0.000013477919503783612",
            "extra": "mean: 245.9347718151026 usec\nrounds: 2292"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 6395.432999351211,
            "unit": "iter/sec",
            "range": "stddev: 0.000017478205387511737",
            "extra": "mean: 156.3615786611236 usec\nrounds: 4780"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 4095.8997436109835,
            "unit": "iter/sec",
            "range": "stddev: 0.000014156455332845228",
            "extra": "mean: 244.1466008927237 usec\nrounds: 3137"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1911.8380528959397,
            "unit": "iter/sec",
            "range": "stddev: 0.000025146731426895443",
            "extra": "mean: 523.0568554095148 usec\nrounds: 989"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1574.5548802667827,
            "unit": "iter/sec",
            "range": "stddev: 0.000015176461818267294",
            "extra": "mean: 635.1001241891081 usec\nrounds: 1079"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1633.9048015894082,
            "unit": "iter/sec",
            "range": "stddev: 0.0004137580533739155",
            "extra": "mean: 612.0307615396156 usec\nrounds: 6781"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 2081.9935210592043,
            "unit": "iter/sec",
            "range": "stddev: 0.000026927386199347226",
            "extra": "mean: 480.3088913990735 usec\nrounds: 1372"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 1516.1764660915612,
            "unit": "iter/sec",
            "range": "stddev: 0.000020298374949475864",
            "extra": "mean: 659.5538331879177 usec\nrounds: 1145"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 95.22874305952796,
            "unit": "iter/sec",
            "range": "stddev: 0.0032555147974898894",
            "extra": "mean: 10.501031178946624 msec\nrounds: 95"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 94.50049898472001,
            "unit": "iter/sec",
            "range": "stddev: 0.003991815255059485",
            "extra": "mean: 10.581954706521625 msec\nrounds: 92"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 126.98505276883148,
            "unit": "iter/sec",
            "range": "stddev: 0.0034941175577272218",
            "extra": "mean: 7.874942587301505 msec\nrounds: 126"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 157.28442540891598,
            "unit": "iter/sec",
            "range": "stddev: 0.0032571246829212605",
            "extra": "mean: 6.357908593938336 msec\nrounds: 165"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 151.95415015368013,
            "unit": "iter/sec",
            "range": "stddev: 0.002925090346128486",
            "extra": "mean: 6.580932465409083 msec\nrounds: 159"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 106.95423521884754,
            "unit": "iter/sec",
            "range": "stddev: 0.0034207165350889804",
            "extra": "mean: 9.349793376146541 msec\nrounds: 109"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 263.213143656612,
            "unit": "iter/sec",
            "range": "stddev: 0.0013286977137456242",
            "extra": "mean: 3.7992023730570255 msec\nrounds: 193"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 71.4502335723707,
            "unit": "iter/sec",
            "range": "stddev: 0.00349387591489122",
            "extra": "mean: 13.995755507042778 msec\nrounds: 71"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10536417706608733,
            "unit": "iter/sec",
            "range": "stddev: 0.018275390264119794",
            "extra": "mean: 9.490891760799993 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 16.661540636886716,
            "unit": "iter/sec",
            "range": "stddev: 0.00040006720273602436",
            "extra": "mean: 60.01845938460913 msec\nrounds: 13"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 55.74504809132695,
            "unit": "iter/sec",
            "range": "stddev: 0.004531809398327594",
            "extra": "mean: 17.938813118641548 msec\nrounds: 59"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 70.88936798194308,
            "unit": "iter/sec",
            "range": "stddev: 0.004091269150640739",
            "extra": "mean: 14.106487735293674 msec\nrounds: 34"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 160.1789408604189,
            "unit": "iter/sec",
            "range": "stddev: 0.001900668568521889",
            "extra": "mean: 6.243017931248573 msec\nrounds: 160"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 140.9552813417394,
            "unit": "iter/sec",
            "range": "stddev: 0.001387301662465199",
            "extra": "mean: 7.094448611510677 msec\nrounds: 139"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 349.4916279753143,
            "unit": "iter/sec",
            "range": "stddev: 0.00002579113065275583",
            "extra": "mean: 2.86129886942709 msec\nrounds: 314"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 1815.4194002277545,
            "unit": "iter/sec",
            "range": "stddev: 0.00002090068837043796",
            "extra": "mean: 550.8369029627779 usec\nrounds: 1350"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 466.3195180491644,
            "unit": "iter/sec",
            "range": "stddev: 0.000026305424689390927",
            "extra": "mean: 2.144452379311666 msec\nrounds: 58"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 213.81157534795616,
            "unit": "iter/sec",
            "range": "stddev: 0.003032149269334443",
            "extra": "mean: 4.677015256880287 msec\nrounds: 218"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 205.5095425693566,
            "unit": "iter/sec",
            "range": "stddev: 0.002939795448707953",
            "extra": "mean: 4.865954093895732 msec\nrounds: 213"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1651.483619311588,
            "unit": "iter/sec",
            "range": "stddev: 0.0005518478831099545",
            "extra": "mean: 605.5161482115363 usec\nrounds: 1174"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 135.36539268849464,
            "unit": "iter/sec",
            "range": "stddev: 0.003909693084275769",
            "extra": "mean: 7.387412544218142 msec\nrounds: 147"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 212.85309340999865,
            "unit": "iter/sec",
            "range": "stddev: 0.002877154234340474",
            "extra": "mean: 4.698075954544834 msec\nrounds: 220"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 73.42212272645854,
            "unit": "iter/sec",
            "range": "stddev: 0.0035320208504179625",
            "extra": "mean: 13.619873178082852 msec\nrounds: 73"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 60.14158113799293,
            "unit": "iter/sec",
            "range": "stddev: 0.003309483456212017",
            "extra": "mean: 16.627431156249983 msec\nrounds: 64"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 85.46922884657876,
            "unit": "iter/sec",
            "range": "stddev: 0.0026596497964998054",
            "extra": "mean: 11.700117264367115 msec\nrounds: 87"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 60.85451382211347,
            "unit": "iter/sec",
            "range": "stddev: 0.002999228594733632",
            "extra": "mean: 16.43263477419513 msec\nrounds: 31"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 100.31975742446741,
            "unit": "iter/sec",
            "range": "stddev: 0.0032571999271321784",
            "extra": "mean: 9.968126176470456 msec\nrounds: 102"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 95.9967985977117,
            "unit": "iter/sec",
            "range": "stddev: 0.0032355079313251263",
            "extra": "mean: 10.417014052631513 msec\nrounds: 95"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 83.33524285985212,
            "unit": "iter/sec",
            "range": "stddev: 0.004740144727826364",
            "extra": "mean: 11.999725034481942 msec\nrounds: 87"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 162.51450206188227,
            "unit": "iter/sec",
            "range": "stddev: 0.0028566271661486396",
            "extra": "mean: 6.153297012344289 msec\nrounds: 162"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 147.518717645207,
            "unit": "iter/sec",
            "range": "stddev: 0.0033609537353937926",
            "extra": "mean: 6.778800791944728 msec\nrounds: 149"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 161.80150190501257,
            "unit": "iter/sec",
            "range": "stddev: 0.0017089480997432805",
            "extra": "mean: 6.180412346154003 msec\nrounds: 156"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 140.8286097682625,
            "unit": "iter/sec",
            "range": "stddev: 0.0013993955809646066",
            "extra": "mean: 7.100829878570331 msec\nrounds: 140"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 42.31360009611091,
            "unit": "iter/sec",
            "range": "stddev: 0.002678508557197326",
            "extra": "mean: 23.633063547620736 msec\nrounds: 42"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 215.04577253787053,
            "unit": "iter/sec",
            "range": "stddev: 0.002929208850493837",
            "extra": "mean: 4.650172789720363 msec\nrounds: 214"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 212.8525866944146,
            "unit": "iter/sec",
            "range": "stddev: 0.0027573388761712894",
            "extra": "mean: 4.698087138756113 msec\nrounds: 209"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 76.48248041815481,
            "unit": "iter/sec",
            "range": "stddev: 0.004666840492695509",
            "extra": "mean: 13.074889759493573 msec\nrounds: 79"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 84.69741426275702,
            "unit": "iter/sec",
            "range": "stddev: 0.0031114215242093192",
            "extra": "mean: 11.806735880952601 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 620005.5150587953,
            "unit": "iter/sec",
            "range": "stddev: 3.3212765351942893e-7",
            "extra": "mean: 1.6128888787467794 usec\nrounds: 65838"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 257360.37473556979,
            "unit": "iter/sec",
            "range": "stddev: 5.742956539384942e-7",
            "extra": "mean: 3.8856020513160607 usec\nrounds: 70592"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 75288.10390378577,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011715221819754408",
            "extra": "mean: 13.282310858538121 usec\nrounds: 34839"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 750289.6376058424,
            "unit": "iter/sec",
            "range": "stddev: 3.305430021730831e-7",
            "extra": "mean: 1.3328186208075294 usec\nrounds: 122175"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2125708.024841922,
            "unit": "iter/sec",
            "range": "stddev: 4.287480705474776e-8",
            "extra": "mean: 470.4314930901034 nsec\nrounds: 100322"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1601668.5048035337,
            "unit": "iter/sec",
            "range": "stddev: 7.804997732577034e-8",
            "extra": "mean: 624.3489192682 nsec\nrounds: 191976"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2345908.732406339,
            "unit": "iter/sec",
            "range": "stddev: 4.884804522600296e-8",
            "extra": "mean: 426.27404305462477 nsec\nrounds: 111396"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 176652.9038024659,
            "unit": "iter/sec",
            "range": "stddev: 7.836438084526352e-7",
            "extra": "mean: 5.660818353250533 usec\nrounds: 90164"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1623.589947236311,
            "unit": "iter/sec",
            "range": "stddev: 0.000010380549178094433",
            "extra": "mean: 615.919063617146 usec\nrounds: 1399"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1641.1437242575369,
            "unit": "iter/sec",
            "range": "stddev: 0.000014088971360489693",
            "extra": "mean: 609.3311543767478 usec\nrounds: 1451"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 436133.75835475064,
            "unit": "iter/sec",
            "range": "stddev: 4.920633338642725e-7",
            "extra": "mean: 2.292874561630703 usec\nrounds: 71860"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 190770.62827208964,
            "unit": "iter/sec",
            "range": "stddev: 8.847290548332856e-7",
            "extra": "mean: 5.241897083725772 usec\nrounds: 63780"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 115853.28943818797,
            "unit": "iter/sec",
            "range": "stddev: 9.330172281753624e-7",
            "extra": "mean: 8.631606446820287 usec\nrounds: 49513"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 324765.92374557327,
            "unit": "iter/sec",
            "range": "stddev: 5.660759190202956e-7",
            "extra": "mean: 3.079140780740949 usec\nrounds: 97286"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 101094.4708404797,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011162431716821434",
            "extra": "mean: 9.89173781400897 usec\nrounds: 47329"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 16065.71268721319,
            "unit": "iter/sec",
            "range": "stddev: 0.0000035563187359448733",
            "extra": "mean: 62.24435974109676 usec\nrounds: 7258"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 10365.1223042825,
            "unit": "iter/sec",
            "range": "stddev: 0.000004053422362581504",
            "extra": "mean: 96.47739511832249 usec\nrounds: 7866"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 12569.098289133592,
            "unit": "iter/sec",
            "range": "stddev: 0.000004279858041719035",
            "extra": "mean: 79.56020209218457 usec\nrounds: 8125"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 89519.88004853885,
            "unit": "iter/sec",
            "range": "stddev: 0.000002042528814217344",
            "extra": "mean: 11.17070308246377 usec\nrounds: 27543"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 25964.800639774505,
            "unit": "iter/sec",
            "range": "stddev: 0.0000023462715231167453",
            "extra": "mean: 38.51367911017724 usec\nrounds: 12992"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 5996.538074115132,
            "unit": "iter/sec",
            "range": "stddev: 0.0000051824881200356584",
            "extra": "mean: 166.76288679240366 usec\nrounds: 3975"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2097.399004379973,
            "unit": "iter/sec",
            "range": "stddev: 0.00001137207283911219",
            "extra": "mean: 476.7810025234645 usec\nrounds: 1585"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 88629.40024456654,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012950809758407797",
            "extra": "mean: 11.282937684792754 usec\nrounds: 34839"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 17514.311167285672,
            "unit": "iter/sec",
            "range": "stddev: 0.0000025014003240810464",
            "extra": "mean: 57.0961649846591 usec\nrounds: 10801"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1310.930358715207,
            "unit": "iter/sec",
            "range": "stddev: 0.00002333857579153232",
            "extra": "mean: 762.817027885495 usec\nrounds: 1040"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 179.36633897416561,
            "unit": "iter/sec",
            "range": "stddev: 0.000022552634027607817",
            "extra": "mean: 5.575182086668065 msec\nrounds: 150"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.39041179212470006,
            "unit": "iter/sec",
            "range": "stddev: 0.025351877169513346",
            "extra": "mean: 2.5613980421999996 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 68345.30184664122,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013366249074610846",
            "extra": "mean: 14.631583634583718 usec\nrounds: 25444"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 6357.133553707723,
            "unit": "iter/sec",
            "range": "stddev: 0.000011134292322468043",
            "extra": "mean: 157.3036009943132 usec\nrounds: 4827"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 157.87626718981267,
            "unit": "iter/sec",
            "range": "stddev: 0.00007017362048877412",
            "extra": "mean: 6.334074258277925 msec\nrounds: 151"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 69322.04364367593,
            "unit": "iter/sec",
            "range": "stddev: 0.000001255626500115057",
            "extra": "mean: 14.425425844917763 usec\nrounds: 28609"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 14597.685437853563,
            "unit": "iter/sec",
            "range": "stddev: 0.0000031729298521609164",
            "extra": "mean: 68.5040107390504 usec\nrounds: 8660"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 2692.45631916041,
            "unit": "iter/sec",
            "range": "stddev: 0.000009781862456845654",
            "extra": "mean: 371.4080681211684 usec\nrounds: 1879"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 777.8515659786444,
            "unit": "iter/sec",
            "range": "stddev: 0.000019643709728305092",
            "extra": "mean: 1.2855923208714792 msec\nrounds: 642"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6025.850268897648,
            "unit": "iter/sec",
            "range": "stddev: 0.000005978908646613685",
            "extra": "mean: 165.95168405718405 usec\nrounds: 4121"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1311.568343220404,
            "unit": "iter/sec",
            "range": "stddev: 0.000009646686770122988",
            "extra": "mean: 762.445971778044 usec\nrounds: 1063"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 158.08928531171998,
            "unit": "iter/sec",
            "range": "stddev: 0.00008236508038956136",
            "extra": "mean: 6.3255393812945835 msec\nrounds: 139"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 2674.2844535539157,
            "unit": "iter/sec",
            "range": "stddev: 0.000010840630659234074",
            "extra": "mean: 373.93180021335354 usec\nrounds: 1872"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 52.515662422655765,
            "unit": "iter/sec",
            "range": "stddev: 0.00029022364121663284",
            "extra": "mean: 19.04193823076657 msec\nrounds: 52"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1216.4195105468707,
            "unit": "iter/sec",
            "range": "stddev: 0.000020614051676075877",
            "extra": "mean: 822.0848081846583 usec\nrounds: 1173"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 392.9068275344328,
            "unit": "iter/sec",
            "range": "stddev: 0.0000765575362447286",
            "extra": "mean: 2.5451326623036703 msec\nrounds: 382"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1460.602392608586,
            "unit": "iter/sec",
            "range": "stddev: 0.000018881743773061326",
            "extra": "mean: 684.6490222530954 usec\nrounds: 1438"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 470.9069207988486,
            "unit": "iter/sec",
            "range": "stddev: 0.00004209292063456411",
            "extra": "mean: 2.1235619096521146 msec\nrounds: 487"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 354.9972449274152,
            "unit": "iter/sec",
            "range": "stddev: 0.00003300329217920938",
            "extra": "mean: 2.816923269938238 msec\nrounds: 326"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1657.4146216755232,
            "unit": "iter/sec",
            "range": "stddev: 0.0009920060631160557",
            "extra": "mean: 603.3493290828303 usec\nrounds: 784"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1333.712988158611,
            "unit": "iter/sec",
            "range": "stddev: 0.000017806048964579494",
            "extra": "mean: 749.7865049516003 usec\nrounds: 1010"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 850.5194093974973,
            "unit": "iter/sec",
            "range": "stddev: 0.0012406394788207734",
            "extra": "mean: 1.1757521215281774 msec\nrounds: 864"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 69.5885359154984,
            "unit": "iter/sec",
            "range": "stddev: 0.008972159983077026",
            "extra": "mean: 14.370183060242905 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 5.894585992824586,
            "unit": "iter/sec",
            "range": "stddev: 0.04550210915810427",
            "extra": "mean: 169.64719849999454 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 266.37121016054004,
            "unit": "iter/sec",
            "range": "stddev: 0.00004836751784474059",
            "extra": "mean: 3.7541594656468584 msec\nrounds: 262"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 69.34392306299306,
            "unit": "iter/sec",
            "range": "stddev: 0.009206406156686388",
            "extra": "mean: 14.420874329414346 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 33.22409735524505,
            "unit": "iter/sec",
            "range": "stddev: 0.013559592120617667",
            "extra": "mean: 30.09863561702245 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 24.300749255488984,
            "unit": "iter/sec",
            "range": "stddev: 0.016077975422007437",
            "extra": "mean: 41.1509945428585 msec\nrounds: 35"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 920.9112942934631,
            "unit": "iter/sec",
            "range": "stddev: 0.0008219817542476978",
            "extra": "mean: 1.0858809162148617 msec\nrounds: 919"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 69.26993678269079,
            "unit": "iter/sec",
            "range": "stddev: 0.009948916350008259",
            "extra": "mean: 14.436277069764564 msec\nrounds: 86"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 6.0087729873226134,
            "unit": "iter/sec",
            "range": "stddev: 0.04194367280743854",
            "extra": "mean: 166.42332837499652 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 271.74615566756216,
            "unit": "iter/sec",
            "range": "stddev: 0.0005706039458160403",
            "extra": "mean: 3.679904863947145 msec\nrounds: 294"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 69.46097709929755,
            "unit": "iter/sec",
            "range": "stddev: 0.00982932700856036",
            "extra": "mean: 14.396572604650459 msec\nrounds: 86"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 33.192207552724234,
            "unit": "iter/sec",
            "range": "stddev: 0.014310954265854865",
            "extra": "mean: 30.127553234039887 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 24.570294669258107,
            "unit": "iter/sec",
            "range": "stddev: 0.01511806165845553",
            "extra": "mean: 40.69955258823905 msec\nrounds: 34"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 16135.648883049702,
            "unit": "iter/sec",
            "range": "stddev: 0.0000032500597160472924",
            "extra": "mean: 61.97457612321296 usec\nrounds: 7547"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 987.0708708572924,
            "unit": "iter/sec",
            "range": "stddev: 0.000011781679102571812",
            "extra": "mean: 1.013098481096376 msec\nrounds: 767"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 72.00101135501654,
            "unit": "iter/sec",
            "range": "stddev: 0.002264248971895849",
            "extra": "mean: 13.888693799997947 msec\nrounds: 55"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1091.0842173683002,
            "unit": "iter/sec",
            "range": "stddev: 0.00001048127228853884",
            "extra": "mean: 916.5195354140529 usec\nrounds: 833"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 977.3791587580807,
            "unit": "iter/sec",
            "range": "stddev: 0.000019061906033070925",
            "extra": "mean: 1.0231443867400065 msec\nrounds: 724"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 923.4265212892112,
            "unit": "iter/sec",
            "range": "stddev: 0.000013630880575929792",
            "extra": "mean: 1.0829231963187318 msec\nrounds: 815"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 908.6459475161315,
            "unit": "iter/sec",
            "range": "stddev: 0.00001785083353943367",
            "extra": "mean: 1.1005386671602877 msec\nrounds: 676"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 179.91231278737908,
            "unit": "iter/sec",
            "range": "stddev: 0.00022615232497547058",
            "extra": "mean: 5.5582632700731445 msec\nrounds: 137"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 159.62738614604717,
            "unit": "iter/sec",
            "range": "stddev: 0.00043779752650467696",
            "extra": "mean: 6.264589204543351 msec\nrounds: 132"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 111.3739949419162,
            "unit": "iter/sec",
            "range": "stddev: 0.0003230581954298887",
            "extra": "mean: 8.978756670455436 msec\nrounds: 88"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 62.66104566558049,
            "unit": "iter/sec",
            "range": "stddev: 0.010858349400086169",
            "extra": "mean: 15.958878269235408 msec\nrounds: 78"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 18.438532704285503,
            "unit": "iter/sec",
            "range": "stddev: 0.018486805231560884",
            "extra": "mean: 54.23425041666027 msec\nrounds: 12"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 6.481742593680877,
            "unit": "iter/sec",
            "range": "stddev: 0.02709798801455283",
            "extra": "mean: 154.27949899999285 msec\nrounds: 6"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.3810624552020205,
            "unit": "iter/sec",
            "range": "stddev: 0.008662329406186463",
            "extra": "mean: 419.9805837999975 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 44.636278653912164,
            "unit": "iter/sec",
            "range": "stddev: 0.01206419267486244",
            "extra": "mean: 22.403301309087844 msec\nrounds: 55"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 14.476366498694471,
            "unit": "iter/sec",
            "range": "stddev: 0.018751872166114517",
            "extra": "mean: 69.07810741667693 msec\nrounds: 12"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 5.989971599816242,
            "unit": "iter/sec",
            "range": "stddev: 0.020841764190297457",
            "extra": "mean: 166.94569971428206 msec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 2.9672917237405256,
            "unit": "iter/sec",
            "range": "stddev: 0.04003179756773895",
            "extra": "mean: 337.00764640000216 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 44.256330126729516,
            "unit": "iter/sec",
            "range": "stddev: 0.012819901210622816",
            "extra": "mean: 22.595637666667475 msec\nrounds: 57"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 428486.257876281,
            "unit": "iter/sec",
            "range": "stddev: 4.4148563491551377e-7",
            "extra": "mean: 2.3337971326229443 usec\nrounds: 92765"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1373369.1160102529,
            "unit": "iter/sec",
            "range": "stddev: 2.469222171716385e-7",
            "extra": "mean: 728.136367959897 nsec\nrounds: 103756"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 120.09077187141183,
            "unit": "iter/sec",
            "range": "stddev: 0.00006353672597160162",
            "extra": "mean: 8.32703449579588 msec\nrounds: 119"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3084413.4867474143,
            "unit": "iter/sec",
            "range": "stddev: 3.566554577727211e-8",
            "extra": "mean: 324.2107468070123 nsec\nrounds: 150989"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 3959347.8043254833,
            "unit": "iter/sec",
            "range": "stddev: 3.1298918417343716e-8",
            "extra": "mean: 252.56684924409177 nsec\nrounds: 190513"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 3676206.493500758,
            "unit": "iter/sec",
            "range": "stddev: 3.325068605216874e-8",
            "extra": "mean: 272.01954018848534 nsec\nrounds: 188680"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 3512450.215378957,
            "unit": "iter/sec",
            "range": "stddev: 5.6745378438034106e-8",
            "extra": "mean: 284.7015441305295 nsec\nrounds: 196464"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3192591.8700248445,
            "unit": "iter/sec",
            "range": "stddev: 4.788445522629697e-8",
            "extra": "mean: 313.2251288957326 nsec\nrounds: 197629"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 29506.45479565359,
            "unit": "iter/sec",
            "range": "stddev: 0.000005277575493401336",
            "extra": "mean: 33.89088953334047 usec\nrounds: 4481"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 30.287783830367832,
            "unit": "iter/sec",
            "range": "stddev: 0.00023512273876811736",
            "extra": "mean: 33.01661176666736 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 5963131.963829287,
            "unit": "iter/sec",
            "range": "stddev: 2.3213643385645767e-8",
            "extra": "mean: 167.6971105227461 nsec\nrounds: 63136"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 32154.893066240085,
            "unit": "iter/sec",
            "range": "stddev: 0.000006122687726628707",
            "extra": "mean: 31.09946588657498 usec\nrounds: 11110"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 32035.54908489408,
            "unit": "iter/sec",
            "range": "stddev: 0.000006272275513869014",
            "extra": "mean: 31.215322620193085 usec\nrounds: 18731"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 32603.04557524209,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034232916383792237",
            "extra": "mean: 30.671981170966866 usec\nrounds: 13596"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 214129.48577271332,
            "unit": "iter/sec",
            "range": "stddev: 8.305514061620275e-7",
            "extra": "mean: 4.6700714588248955 usec\nrounds: 75330"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 214424.2528336714,
            "unit": "iter/sec",
            "range": "stddev: 8.223888182789898e-7",
            "extra": "mean: 4.663651554265639 usec\nrounds: 113174"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 214630.55397568378,
            "unit": "iter/sec",
            "range": "stddev: 8.023720510914643e-7",
            "extra": "mean: 4.6591688903402515 usec\nrounds: 113174"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 186006.06709692595,
            "unit": "iter/sec",
            "range": "stddev: 8.948831435120193e-7",
            "extra": "mean: 5.376168721845561 usec\nrounds: 21977"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 222.9269875683183,
            "unit": "iter/sec",
            "range": "stddev: 0.00003450737709036948",
            "extra": "mean: 4.485773619910149 msec\nrounds: 221"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 33006.95564150982,
            "unit": "iter/sec",
            "range": "stddev: 0.0000035168781791639613",
            "extra": "mean: 30.296644466731486 usec\nrounds: 8919"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 33010.71377187662,
            "unit": "iter/sec",
            "range": "stddev: 0.000003932486287787822",
            "extra": "mean: 30.29319532169423 usec\nrounds: 15390"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 32447.10150461172,
            "unit": "iter/sec",
            "range": "stddev: 0.000006236047279587706",
            "extra": "mean: 30.819393832693173 usec\nrounds: 13912"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 32274.243382297926,
            "unit": "iter/sec",
            "range": "stddev: 0.000004784772822978793",
            "extra": "mean: 30.984459903666995 usec\nrounds: 10400"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.417219483247829,
            "unit": "iter/sec",
            "range": "stddev: 0.0017957194211310318",
            "extra": "mean: 292.6355784000066 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 26550.348681387266,
            "unit": "iter/sec",
            "range": "stddev: 0.000006346752554842034",
            "extra": "mean: 37.66428878205413 usec\nrounds: 10198"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 26783.477646549487,
            "unit": "iter/sec",
            "range": "stddev: 0.000003943258543262052",
            "extra": "mean: 37.336450971624664 usec\nrounds: 13329"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 26786.068518341817,
            "unit": "iter/sec",
            "range": "stddev: 0.0000036617444237479927",
            "extra": "mean: 37.33283961829814 usec\nrounds: 12994"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 173050.3963201408,
            "unit": "iter/sec",
            "range": "stddev: 9.794938634012793e-7",
            "extra": "mean: 5.778663448710132 usec\nrounds: 30349"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 19339.97072593981,
            "unit": "iter/sec",
            "range": "stddev: 0.000003107242667616512",
            "extra": "mean: 51.706386435153505 usec\nrounds: 10188"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1941.296261607199,
            "unit": "iter/sec",
            "range": "stddev: 0.000008502021077445944",
            "extra": "mean: 515.1197268427746 usec\nrounds: 1900"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 204504.45257184387,
            "unit": "iter/sec",
            "range": "stddev: 8.94775044584671e-7",
            "extra": "mean: 4.889869083161859 usec\nrounds: 27781"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 3238.182355751127,
            "unit": "iter/sec",
            "range": "stddev: 0.00000743761186291654",
            "extra": "mean: 308.8152210526268 usec\nrounds: 2375"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 1659.266093487456,
            "unit": "iter/sec",
            "range": "stddev: 0.000044589926933163366",
            "extra": "mean: 602.6760891004491 usec\nrounds: 1257"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 611.5319030162524,
            "unit": "iter/sec",
            "range": "stddev: 0.000014993301096309249",
            "extra": "mean: 1.6352376631009937 msec\nrounds: 561"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 48290.77697275351,
            "unit": "iter/sec",
            "range": "stddev: 0.000001955933205555994",
            "extra": "mean: 20.70788797960773 usec\nrounds: 15274"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 29.846658858590754,
            "unit": "iter/sec",
            "range": "stddev: 0.00014189247592219552",
            "extra": "mean: 33.504587724135504 msec\nrounds: 29"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 21924.75367031224,
            "unit": "iter/sec",
            "range": "stddev: 0.000003748581878698968",
            "extra": "mean: 45.61054664682846 usec\nrounds: 10140"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 8279.200149515415,
            "unit": "iter/sec",
            "range": "stddev: 0.0000071398076500878105",
            "extra": "mean: 120.78461468992634 usec\nrounds: 5759"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 12135.897839338046,
            "unit": "iter/sec",
            "range": "stddev: 0.000003611313873687366",
            "extra": "mean: 82.4001662867117 usec\nrounds: 9207"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3514.412530744163,
            "unit": "iter/sec",
            "range": "stddev: 0.00012231108457782267",
            "extra": "mean: 284.5425775295235 usec\nrounds: 1967"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 2067917.8049830014,
            "unit": "iter/sec",
            "range": "stddev: 3.977477381506849e-8",
            "extra": "mean: 483.57821456458714 nsec\nrounds: 50209"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1852448.0928779612,
            "unit": "iter/sec",
            "range": "stddev: 7.477929751707034e-8",
            "extra": "mean: 539.8261920777501 nsec\nrounds: 198020"
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
          "id": "6c8b0a5d8cf949e34d8d608b133815a0b327a127",
          "message": "Add .playwright-mcp/ to .gitignore",
          "timestamp": "2026-03-13T15:09:55+09:00",
          "tree_id": "ed12c14dbea30784a4989e339f270f8b0c0a034c",
          "url": "https://github.com/cognica-io/uqa/commit/6c8b0a5d8cf949e34d8d608b133815a0b327a127"
        },
        "date": 1773382539053,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 17988.774917074228,
            "unit": "iter/sec",
            "range": "stddev: 0.000004410172780371568",
            "extra": "mean: 55.590222492074204 usec\nrounds: 2881"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 5797.478800207614,
            "unit": "iter/sec",
            "range": "stddev: 0.000008439941150756041",
            "extra": "mean: 172.48877218217493 usec\nrounds: 3336"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 8973.818555087348,
            "unit": "iter/sec",
            "range": "stddev: 0.000005968120931334598",
            "extra": "mean: 111.43528185480082 usec\nrounds: 5219"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 3765.156453156989,
            "unit": "iter/sec",
            "range": "stddev: 0.000011471535535044212",
            "extra": "mean: 265.593213042057 usec\nrounds: 2699"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 8567.417919743419,
            "unit": "iter/sec",
            "range": "stddev: 0.00000658834270520707",
            "extra": "mean: 116.72128164724204 usec\nrounds: 5901"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 5641.817906510922,
            "unit": "iter/sec",
            "range": "stddev: 0.00007607249187819742",
            "extra": "mean: 177.2478333350591 usec\nrounds: 6"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 2506.7545471536882,
            "unit": "iter/sec",
            "range": "stddev: 0.000013118575686764002",
            "extra": "mean: 398.92218451760937 usec\nrounds: 1886"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4483.292874592855,
            "unit": "iter/sec",
            "range": "stddev: 0.00012350366569527203",
            "extra": "mean: 223.05034000055457 usec\nrounds: 50"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 4999.8612783536,
            "unit": "iter/sec",
            "range": "stddev: 0.000018997684597046534",
            "extra": "mean: 200.00554901980985 usec\nrounds: 204"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 3666.7624218604287,
            "unit": "iter/sec",
            "range": "stddev: 0.00024422231776481375",
            "extra": "mean: 272.72015062612746 usec\nrounds: 3034"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 9071.761767489106,
            "unit": "iter/sec",
            "range": "stddev: 0.000018107503508534438",
            "extra": "mean: 110.23217161453097 usec\nrounds: 5221"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 6754.182209736251,
            "unit": "iter/sec",
            "range": "stddev: 0.00002186038403660426",
            "extra": "mean: 148.05641437367288 usec\nrounds: 4870"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 5879.052499339096,
            "unit": "iter/sec",
            "range": "stddev: 0.000016068838313289198",
            "extra": "mean: 170.09543631604186 usec\nrounds: 3431"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 5287.633002974299,
            "unit": "iter/sec",
            "range": "stddev: 0.000016001226850081222",
            "extra": "mean: 189.12053832735722 usec\nrounds: 4018"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 3804.623282658929,
            "unit": "iter/sec",
            "range": "stddev: 0.000015736022966028655",
            "extra": "mean: 262.83811187244066 usec\nrounds: 876"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1393.0418037702757,
            "unit": "iter/sec",
            "range": "stddev: 0.000043091389359921926",
            "extra": "mean: 717.8535470317504 usec\nrounds: 1095"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 8935.57073216523,
            "unit": "iter/sec",
            "range": "stddev: 0.000008426409222213919",
            "extra": "mean: 111.91226950958108 usec\nrounds: 5792"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 7756.469299325823,
            "unit": "iter/sec",
            "range": "stddev: 0.000010206076592246162",
            "extra": "mean: 128.92463844173508 usec\nrounds: 6212"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 4038.6645226942355,
            "unit": "iter/sec",
            "range": "stddev: 0.000014596923526829757",
            "extra": "mean: 247.6066022272356 usec\nrounds: 2245"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 6384.386138552616,
            "unit": "iter/sec",
            "range": "stddev: 0.000017146836007049782",
            "extra": "mean: 156.63213005889816 usec\nrounds: 4744"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 4069.0511583130306,
            "unit": "iter/sec",
            "range": "stddev: 0.00001344901674695189",
            "extra": "mean: 245.75753931159358 usec\nrounds: 3167"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1916.2239073725398,
            "unit": "iter/sec",
            "range": "stddev: 0.000018148426816778403",
            "extra": "mean: 521.8596825520069 usec\nrounds: 1301"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1567.2495282834109,
            "unit": "iter/sec",
            "range": "stddev: 0.000023299308982104566",
            "extra": "mean: 638.060488743798 usec\nrounds: 1377"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1643.397038222825,
            "unit": "iter/sec",
            "range": "stddev: 0.0004132045831853775",
            "extra": "mean: 608.4956810445535 usec\nrounds: 6816"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 2104.563308825931,
            "unit": "iter/sec",
            "range": "stddev: 0.000022232046566476613",
            "extra": "mean: 475.15795595518017 usec\nrounds: 1612"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 1501.3637976916966,
            "unit": "iter/sec",
            "range": "stddev: 0.000035154280911682576",
            "extra": "mean: 666.0610849532079 usec\nrounds: 1389"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 94.54529848102565,
            "unit": "iter/sec",
            "range": "stddev: 0.002960355574976062",
            "extra": "mean: 10.576940536082718 msec\nrounds: 97"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 97.44883885408248,
            "unit": "iter/sec",
            "range": "stddev: 0.0029364996147252004",
            "extra": "mean: 10.261794925000345 msec\nrounds: 40"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 127.14859411175317,
            "unit": "iter/sec",
            "range": "stddev: 0.003419745827383014",
            "extra": "mean: 7.864813661416359 msec\nrounds: 127"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 163.45760022312527,
            "unit": "iter/sec",
            "range": "stddev: 0.002630206982571847",
            "extra": "mean: 6.11779445333203 msec\nrounds: 150"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 151.04236360694074,
            "unit": "iter/sec",
            "range": "stddev: 0.0026370683826257065",
            "extra": "mean: 6.62065910595991 msec\nrounds: 151"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 106.96183013033433,
            "unit": "iter/sec",
            "range": "stddev: 0.0035719517002214536",
            "extra": "mean: 9.349129486485856 msec\nrounds: 111"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 266.8425818118417,
            "unit": "iter/sec",
            "range": "stddev: 0.0012122030413458656",
            "extra": "mean: 3.747527824120397 msec\nrounds: 199"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 70.75941254209744,
            "unit": "iter/sec",
            "range": "stddev: 0.003798964205056937",
            "extra": "mean: 14.132395452054698 msec\nrounds: 73"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10606234094963603,
            "unit": "iter/sec",
            "range": "stddev: 0.03103072932635288",
            "extra": "mean: 9.428417203000004 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 16.40841933253811,
            "unit": "iter/sec",
            "range": "stddev: 0.0008503117951488555",
            "extra": "mean: 60.944322529409455 msec\nrounds: 17"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 56.1411254802625,
            "unit": "iter/sec",
            "range": "stddev: 0.0039031673296996685",
            "extra": "mean: 17.81225423333505 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 71.28826259557162,
            "unit": "iter/sec",
            "range": "stddev: 0.0034210555414469334",
            "extra": "mean: 14.027554657533752 msec\nrounds: 73"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 159.9326932145456,
            "unit": "iter/sec",
            "range": "stddev: 0.0017072747622682459",
            "extra": "mean: 6.252630277778951 msec\nrounds: 162"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 136.29198408822506,
            "unit": "iter/sec",
            "range": "stddev: 0.0017502737582024816",
            "extra": "mean: 7.337188659258757 msec\nrounds: 135"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 345.87993322407004,
            "unit": "iter/sec",
            "range": "stddev: 0.00003390691135035624",
            "extra": "mean: 2.891176688623257 msec\nrounds: 334"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 1815.9894882003803,
            "unit": "iter/sec",
            "range": "stddev: 0.000018873088364806104",
            "extra": "mean: 550.6639804347027 usec\nrounds: 1380"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 445.2492397994245,
            "unit": "iter/sec",
            "range": "stddev: 0.0012186495874720463",
            "extra": "mean: 2.245933087837453 msec\nrounds: 444"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 222.2815695014702,
            "unit": "iter/sec",
            "range": "stddev: 0.002110947708086475",
            "extra": "mean: 4.498798538460859 msec\nrounds: 221"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 207.48624503586058,
            "unit": "iter/sec",
            "range": "stddev: 0.0024461324217824316",
            "extra": "mean: 4.819596594594338 msec\nrounds: 222"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1696.2572709119427,
            "unit": "iter/sec",
            "range": "stddev: 0.000018085704668837333",
            "extra": "mean: 589.5332135922869 usec\nrounds: 1442"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 137.487307545489,
            "unit": "iter/sec",
            "range": "stddev: 0.0032677644186198305",
            "extra": "mean: 7.273398671140173 msec\nrounds: 149"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 216.3946206845672,
            "unit": "iter/sec",
            "range": "stddev: 0.0024178464081993953",
            "extra": "mean: 4.621186963134698 msec\nrounds: 217"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 74.87131193774721,
            "unit": "iter/sec",
            "range": "stddev: 0.002897764158255697",
            "extra": "mean: 13.356250533334634 msec\nrounds: 75"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 58.43819163194434,
            "unit": "iter/sec",
            "range": "stddev: 0.004209157804771507",
            "extra": "mean: 17.112096936506934 msec\nrounds: 63"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 81.23292619883854,
            "unit": "iter/sec",
            "range": "stddev: 0.003907001703651084",
            "extra": "mean: 12.31027917857153 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 59.1635653331086,
            "unit": "iter/sec",
            "range": "stddev: 0.003929210711532805",
            "extra": "mean: 16.90229441666844 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 101.33175983540511,
            "unit": "iter/sec",
            "range": "stddev: 0.0026909230979727957",
            "extra": "mean: 9.86857429126186 msec\nrounds: 103"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 95.84311669470344,
            "unit": "iter/sec",
            "range": "stddev: 0.002965601327710253",
            "extra": "mean: 10.433717459182573 msec\nrounds: 98"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 85.47297393711142,
            "unit": "iter/sec",
            "range": "stddev: 0.0034875618653396317",
            "extra": "mean: 11.699604611111011 msec\nrounds: 90"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 161.68861986604549,
            "unit": "iter/sec",
            "range": "stddev: 0.002790410397904815",
            "extra": "mean: 6.184727167740514 msec\nrounds: 155"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 150.64315327129555,
            "unit": "iter/sec",
            "range": "stddev: 0.0028348460041631943",
            "extra": "mean: 6.638204115384419 msec\nrounds: 156"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 163.52944243768707,
            "unit": "iter/sec",
            "range": "stddev: 0.00006807152005151251",
            "extra": "mean: 6.115106766667111 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 138.1409003161288,
            "unit": "iter/sec",
            "range": "stddev: 0.0016595332496407037",
            "extra": "mean: 7.238985685713268 msec\nrounds: 140"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 42.8853947387583,
            "unit": "iter/sec",
            "range": "stddev: 0.00025572166741929175",
            "extra": "mean: 23.317961886363037 msec\nrounds: 44"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 226.00287603586935,
            "unit": "iter/sec",
            "range": "stddev: 0.001728713753408396",
            "extra": "mean: 4.424722452829707 msec\nrounds: 53"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 216.34881392232018,
            "unit": "iter/sec",
            "range": "stddev: 0.002284236158281105",
            "extra": "mean: 4.622165390557903 msec\nrounds: 233"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 78.4010082247232,
            "unit": "iter/sec",
            "range": "stddev: 0.0035939871857412365",
            "extra": "mean: 12.754938012195833 msec\nrounds: 82"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 85.30964575894835,
            "unit": "iter/sec",
            "range": "stddev: 0.002344242602059359",
            "extra": "mean: 11.7220038965536 msec\nrounds: 87"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 629711.9629496044,
            "unit": "iter/sec",
            "range": "stddev: 3.7042885613693886e-7",
            "extra": "mean: 1.588027636184561 usec\nrounds: 68461"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 258547.48940501234,
            "unit": "iter/sec",
            "range": "stddev: 5.733591477658636e-7",
            "extra": "mean: 3.8677614015950037 usec\nrounds: 81480"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 77908.40789527424,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011371566687132234",
            "extra": "mean: 12.835585105836284 usec\nrounds: 36954"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 762056.2327258288,
            "unit": "iter/sec",
            "range": "stddev: 3.4411692803357947e-7",
            "extra": "mean: 1.3122391197078211 usec\nrounds: 174490"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2165329.7706813766,
            "unit": "iter/sec",
            "range": "stddev: 6.369194889653357e-8",
            "extra": "mean: 461.82341994278516 nsec\nrounds: 191939"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1683928.3180558456,
            "unit": "iter/sec",
            "range": "stddev: 7.204196474350631e-8",
            "extra": "mean: 593.8495061087488 nsec\nrounds: 176648"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2502576.8953776597,
            "unit": "iter/sec",
            "range": "stddev: 4.3738523258300244e-8",
            "extra": "mean: 399.5881212869152 nsec\nrounds: 114983"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 174574.6418040534,
            "unit": "iter/sec",
            "range": "stddev: 6.970573331532622e-7",
            "extra": "mean: 5.728208803214519 usec\nrounds: 93284"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1587.0744682975726,
            "unit": "iter/sec",
            "range": "stddev: 0.000008858921229891188",
            "extra": "mean: 630.0901564327241 usec\nrounds: 1368"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1602.8459836848576,
            "unit": "iter/sec",
            "range": "stddev: 0.00003640459328131896",
            "extra": "mean: 623.8902615590384 usec\nrounds: 1449"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 445166.0613155921,
            "unit": "iter/sec",
            "range": "stddev: 5.062234034989743e-7",
            "extra": "mean: 2.246352736425405 usec\nrounds: 62035"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 192375.2334924546,
            "unit": "iter/sec",
            "range": "stddev: 8.144218147554531e-7",
            "extra": "mean: 5.198174327566039 usec\nrounds: 70792"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 115281.9477751956,
            "unit": "iter/sec",
            "range": "stddev: 9.761892462335224e-7",
            "extra": "mean: 8.674385012561029 usec\nrounds: 54245"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 336491.4149690867,
            "unit": "iter/sec",
            "range": "stddev: 5.371529868754775e-7",
            "extra": "mean: 2.9718440219102455 usec\nrounds: 108496"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 101727.49256326442,
            "unit": "iter/sec",
            "range": "stddev: 9.896114512793933e-7",
            "extra": "mean: 9.830184297308804 usec\nrounds: 50310"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 15062.272248689791,
            "unit": "iter/sec",
            "range": "stddev: 0.000004445860004250256",
            "extra": "mean: 66.39104535419523 usec\nrounds: 6791"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 10413.145100155549,
            "unit": "iter/sec",
            "range": "stddev: 0.000005804845749201817",
            "extra": "mean: 96.03246573266921 usec\nrounds: 7850"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 12638.094047826093,
            "unit": "iter/sec",
            "range": "stddev: 0.000004030881219796821",
            "extra": "mean: 79.12585522909701 usec\nrounds: 8137"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 92896.61320352367,
            "unit": "iter/sec",
            "range": "stddev: 0.000001176479481680229",
            "extra": "mean: 10.764655088223053 usec\nrounds: 25392"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 26651.839035360328,
            "unit": "iter/sec",
            "range": "stddev: 0.0000019303743980059143",
            "extra": "mean: 37.520862957083374 usec\nrounds: 1941"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 6081.916177870135,
            "unit": "iter/sec",
            "range": "stddev: 0.0000059923567526419835",
            "extra": "mean: 164.42186487847923 usec\nrounds: 4063"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 1924.5223877175993,
            "unit": "iter/sec",
            "range": "stddev: 0.00006508550494304014",
            "extra": "mean: 519.609439922368 usec\nrounds: 1548"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 90455.37214391794,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012698334714138921",
            "extra": "mean: 11.0551753455722 usec\nrounds: 35815"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 18286.876279984415,
            "unit": "iter/sec",
            "range": "stddev: 0.0000028087470624675894",
            "extra": "mean: 54.68402501823303 usec\nrounds: 6875"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1347.9259196599303,
            "unit": "iter/sec",
            "range": "stddev: 0.000013610936220784342",
            "extra": "mean: 741.8805332063731 usec\nrounds: 1054"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 185.18564725859497,
            "unit": "iter/sec",
            "range": "stddev: 0.000045437037816504945",
            "extra": "mean: 5.399986525972992 msec\nrounds: 154"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.3912996314099666,
            "unit": "iter/sec",
            "range": "stddev: 0.034167965684051366",
            "extra": "mean: 2.555586358200003 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 71454.46057877419,
            "unit": "iter/sec",
            "range": "stddev: 0.000003319897260321206",
            "extra": "mean: 13.994927565054683 usec\nrounds: 27183"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 6549.041784690767,
            "unit": "iter/sec",
            "range": "stddev: 0.00001408952874385289",
            "extra": "mean: 152.69409371270612 usec\nrounds: 5026"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 161.84237254087978,
            "unit": "iter/sec",
            "range": "stddev: 0.000042579811616678446",
            "extra": "mean: 6.178851584416868 msec\nrounds: 154"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 73212.81286804115,
            "unit": "iter/sec",
            "range": "stddev: 0.0000012452330633433816",
            "extra": "mean: 13.658811358640204 usec\nrounds: 30338"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 15105.302997899875,
            "unit": "iter/sec",
            "range": "stddev: 0.0000038967307522343",
            "extra": "mean: 66.20191598533525 usec\nrounds: 7582"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 2753.047530490676,
            "unit": "iter/sec",
            "range": "stddev: 0.00002482819100260579",
            "extra": "mean: 363.2338304823128 usec\nrounds: 1929"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 790.557975843685,
            "unit": "iter/sec",
            "range": "stddev: 0.000024974001793603093",
            "extra": "mean: 1.2649293670496438 msec\nrounds: 613"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6222.228765906655,
            "unit": "iter/sec",
            "range": "stddev: 0.000005804062189995854",
            "extra": "mean: 160.7141166971041 usec\nrounds: 4276"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1365.1800426947702,
            "unit": "iter/sec",
            "range": "stddev: 0.00003315353167736372",
            "extra": "mean: 732.5041157399794 usec\nrounds: 1080"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 160.95321346367635,
            "unit": "iter/sec",
            "range": "stddev: 0.000053241866059539826",
            "extra": "mean: 6.212985615386165 msec\nrounds: 143"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 2755.100079527345,
            "unit": "iter/sec",
            "range": "stddev: 0.000010026564634011506",
            "extra": "mean: 362.96322134750056 usec\nrounds: 2033"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 54.25772397182531,
            "unit": "iter/sec",
            "range": "stddev: 0.0001787492827535675",
            "extra": "mean: 18.43055562963303 msec\nrounds: 54"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1236.2394510899344,
            "unit": "iter/sec",
            "range": "stddev: 0.00001371865347394609",
            "extra": "mean: 808.904779020235 usec\nrounds: 1163"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 399.271361543868,
            "unit": "iter/sec",
            "range": "stddev: 0.00003157845161739735",
            "extra": "mean: 2.5045623010207554 msec\nrounds: 392"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1449.5637236926555,
            "unit": "iter/sec",
            "range": "stddev: 0.000012259854013848611",
            "extra": "mean: 689.8627384607657 usec\nrounds: 1365"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 487.2347271929513,
            "unit": "iter/sec",
            "range": "stddev: 0.000019141490436589",
            "extra": "mean: 2.052398862784645 msec\nrounds: 481"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 351.6256949923717,
            "unit": "iter/sec",
            "range": "stddev: 0.00006664679321686831",
            "extra": "mean: 2.8439332342356107 msec\nrounds: 333"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1748.9068750868719,
            "unit": "iter/sec",
            "range": "stddev: 0.00001744052805749858",
            "extra": "mean: 571.7857332742934 usec\nrounds: 1121"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1326.012835555706,
            "unit": "iter/sec",
            "range": "stddev: 0.000018087080511575076",
            "extra": "mean: 754.140512961867 usec\nrounds: 1080"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 824.7588025870285,
            "unit": "iter/sec",
            "range": "stddev: 0.001376686208831947",
            "extra": "mean: 1.2124756921214916 msec\nrounds: 825"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 71.21531341796879,
            "unit": "iter/sec",
            "range": "stddev: 0.008472475811103858",
            "extra": "mean: 14.041923738099896 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 5.912601737759457,
            "unit": "iter/sec",
            "range": "stddev: 0.04665371843875412",
            "extra": "mean: 169.13028212499626 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 266.075949308334,
            "unit": "iter/sec",
            "range": "stddev: 0.00004210989488780949",
            "extra": "mean: 3.7583254052066937 msec\nrounds: 269"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 67.00417052442121,
            "unit": "iter/sec",
            "range": "stddev: 0.010477761891572788",
            "extra": "mean: 14.924444137929102 msec\nrounds: 87"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 33.88719174510975,
            "unit": "iter/sec",
            "range": "stddev: 0.014118053669943233",
            "extra": "mean: 29.50967455555858 msec\nrounds: 18"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 24.389880093809705,
            "unit": "iter/sec",
            "range": "stddev: 0.016239639853075496",
            "extra": "mean: 41.00061157142818 msec\nrounds: 35"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 912.484166446095,
            "unit": "iter/sec",
            "range": "stddev: 0.0009829712151987195",
            "extra": "mean: 1.095909427003822 msec\nrounds: 911"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 68.99549924996708,
            "unit": "iter/sec",
            "range": "stddev: 0.010499666786911048",
            "extra": "mean: 14.493699021976092 msec\nrounds: 91"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 5.855775166505223,
            "unit": "iter/sec",
            "range": "stddev: 0.04517288505785906",
            "extra": "mean: 170.7715838750019 msec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 287.87170216840855,
            "unit": "iter/sec",
            "range": "stddev: 0.000047296704490479126",
            "extra": "mean: 3.473769712227524 msec\nrounds: 278"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 66.79054259981132,
            "unit": "iter/sec",
            "range": "stddev: 0.011286539925138273",
            "extra": "mean: 14.972179609195525 msec\nrounds: 87"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 34.57610742359449,
            "unit": "iter/sec",
            "range": "stddev: 0.013573992606625087",
            "extra": "mean: 28.921705608700393 msec\nrounds: 46"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 22.296681508400315,
            "unit": "iter/sec",
            "range": "stddev: 0.019008204196373838",
            "extra": "mean: 44.84972347222379 msec\nrounds: 36"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 16201.435006785468,
            "unit": "iter/sec",
            "range": "stddev: 0.000003273081545541043",
            "extra": "mean: 61.722927603708 usec\nrounds: 10774"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 970.1542812158929,
            "unit": "iter/sec",
            "range": "stddev: 0.000015578675250786488",
            "extra": "mean: 1.030763889168949 msec\nrounds: 794"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 71.31303088944328,
            "unit": "iter/sec",
            "range": "stddev: 0.001998446852026872",
            "extra": "mean: 14.022682636365598 msec\nrounds: 55"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1097.8923188478598,
            "unit": "iter/sec",
            "range": "stddev: 0.000015601042915550954",
            "extra": "mean: 910.8361383285848 usec\nrounds: 694"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 975.4949095905238,
            "unit": "iter/sec",
            "range": "stddev: 0.000013778258988572337",
            "extra": "mean: 1.0251206748170143 msec\nrounds: 818"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 909.9997470910317,
            "unit": "iter/sec",
            "range": "stddev: 0.000013544567847416354",
            "extra": "mean: 1.0989014043099126 msec\nrounds: 789"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 904.0696841352698,
            "unit": "iter/sec",
            "range": "stddev: 0.000018828167769572242",
            "extra": "mean: 1.1061094266826195 msec\nrounds: 757"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 163.67886366598813,
            "unit": "iter/sec",
            "range": "stddev: 0.0005137352102368497",
            "extra": "mean: 6.109524330769143 msec\nrounds: 130"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 156.09469397768183,
            "unit": "iter/sec",
            "range": "stddev: 0.00038378748920106395",
            "extra": "mean: 6.4063676638680525 msec\nrounds: 119"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 105.85167610246177,
            "unit": "iter/sec",
            "range": "stddev: 0.0007034173244055786",
            "extra": "mean: 9.447181535718197 msec\nrounds: 84"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 60.42310831318632,
            "unit": "iter/sec",
            "range": "stddev: 0.012617337795403038",
            "extra": "mean: 16.549959575346225 msec\nrounds: 73"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 17.808028526469183,
            "unit": "iter/sec",
            "range": "stddev: 0.022063550233700453",
            "extra": "mean: 56.154447333327084 msec\nrounds: 12"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 6.527325044930479,
            "unit": "iter/sec",
            "range": "stddev: 0.026647214443613277",
            "extra": "mean: 153.20211466665987 msec\nrounds: 6"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.441138577009501,
            "unit": "iter/sec",
            "range": "stddev: 0.003123030386932177",
            "extra": "mean: 409.64491299999963 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 44.74144608445042,
            "unit": "iter/sec",
            "range": "stddev: 0.012456937694065463",
            "extra": "mean: 22.350641016664476 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 14.361859861369743,
            "unit": "iter/sec",
            "range": "stddev: 0.01945750483253337",
            "extra": "mean: 69.62886489999676 msec\nrounds: 20"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 6.213470110486317,
            "unit": "iter/sec",
            "range": "stddev: 0.017454512586928143",
            "extra": "mean: 160.9406631428588 msec\nrounds: 7"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 3.030606680561773,
            "unit": "iter/sec",
            "range": "stddev: 0.03744503494541327",
            "extra": "mean: 329.9669358000074 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 47.02405899297464,
            "unit": "iter/sec",
            "range": "stddev: 0.010848642536755701",
            "extra": "mean: 21.2657099666662 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 418352.2416000657,
            "unit": "iter/sec",
            "range": "stddev: 4.356393272882535e-7",
            "extra": "mean: 2.3903302063718233 usec\nrounds: 82830"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1366758.4247056805,
            "unit": "iter/sec",
            "range": "stddev: 2.7096487808139177e-7",
            "extra": "mean: 731.6581935211713 nsec\nrounds: 100121"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 117.89700938346805,
            "unit": "iter/sec",
            "range": "stddev: 0.00006564444330918047",
            "extra": "mean: 8.481979358334968 msec\nrounds: 120"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3286479.824372498,
            "unit": "iter/sec",
            "range": "stddev: 4.2775374037980584e-8",
            "extra": "mean: 304.2769325963942 nsec\nrounds: 195351"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4321411.8537926655,
            "unit": "iter/sec",
            "range": "stddev: 2.7520846460984185e-8",
            "extra": "mean: 231.4058538813779 nsec\nrounds: 194932"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4092500.5519752465,
            "unit": "iter/sec",
            "range": "stddev: 3.971083377941689e-8",
            "extra": "mean: 244.34938671354598 nsec\nrounds: 189036"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 3926481.753884182,
            "unit": "iter/sec",
            "range": "stddev: 3.0339736324163586e-8",
            "extra": "mean: 254.68092370753362 nsec\nrounds: 194553"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3437856.0197942755,
            "unit": "iter/sec",
            "range": "stddev: 3.679468955221239e-8",
            "extra": "mean: 290.87896475078117 nsec\nrounds: 199204"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 29495.23983310148,
            "unit": "iter/sec",
            "range": "stddev: 0.000003143781539745687",
            "extra": "mean: 33.903775851916784 usec\nrounds: 5019"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 30.043550349452296,
            "unit": "iter/sec",
            "range": "stddev: 0.00021263878678727443",
            "extra": "mean: 33.28501420000217 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 6553160.708452594,
            "unit": "iter/sec",
            "range": "stddev: 1.9698752682019187e-8",
            "extra": "mean: 152.59811936401164 nsec\nrounds: 194970"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 32390.84292566018,
            "unit": "iter/sec",
            "range": "stddev: 0.0000032812269855213073",
            "extra": "mean: 30.87292301392364 usec\nrounds: 10963"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 32269.422058898424,
            "unit": "iter/sec",
            "range": "stddev: 0.000004866871433853016",
            "extra": "mean: 30.989089242899716 usec\nrounds: 18007"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 32042.548772780337,
            "unit": "iter/sec",
            "range": "stddev: 0.000003333109879041172",
            "extra": "mean: 31.208503639681897 usec\nrounds: 13601"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 212569.97340732036,
            "unit": "iter/sec",
            "range": "stddev: 7.241769114741514e-7",
            "extra": "mean: 4.70433327892378 usec\nrounds: 79720"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 213150.27968323042,
            "unit": "iter/sec",
            "range": "stddev: 7.281670876981858e-7",
            "extra": "mean: 4.691525629176431 usec\nrounds: 111396"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 212325.71236938384,
            "unit": "iter/sec",
            "range": "stddev: 7.726962144071617e-7",
            "extra": "mean: 4.709745178013561 usec\nrounds: 111521"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 182179.23349930008,
            "unit": "iter/sec",
            "range": "stddev: 8.2429754591321e-7",
            "extra": "mean: 5.489099832028011 usec\nrounds: 23840"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 220.22234877164604,
            "unit": "iter/sec",
            "range": "stddev: 0.000027181567529350266",
            "extra": "mean: 4.54086520091076 msec\nrounds: 219"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 32518.540502356293,
            "unit": "iter/sec",
            "range": "stddev: 0.0000033993865131536722",
            "extra": "mean: 30.751687638857597 usec\nrounds: 9441"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 32519.898308051113,
            "unit": "iter/sec",
            "range": "stddev: 0.000003720439973121524",
            "extra": "mean: 30.75040366139229 usec\nrounds: 15897"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 32412.715518571807,
            "unit": "iter/sec",
            "range": "stddev: 0.0000038013892321018435",
            "extra": "mean: 30.8520894963898 usec\nrounds: 15766"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 31981.122228415756,
            "unit": "iter/sec",
            "range": "stddev: 0.0000035205694847870152",
            "extra": "mean: 31.268446205789594 usec\nrounds: 15643"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.354895562473607,
            "unit": "iter/sec",
            "range": "stddev: 0.00036780968381966596",
            "extra": "mean: 298.07187179999346 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 26550.81136431615,
            "unit": "iter/sec",
            "range": "stddev: 0.00000388815302208786",
            "extra": "mean: 37.66363243211405 usec\nrounds: 10175"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 26525.26420687068,
            "unit": "iter/sec",
            "range": "stddev: 0.000004296297438936094",
            "extra": "mean: 37.69990723564503 usec\nrounds: 10974"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 26388.12272075227,
            "unit": "iter/sec",
            "range": "stddev: 0.000003824101946322529",
            "extra": "mean: 37.895837099983446 usec\nrounds: 13407"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 180415.53301534583,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010729654819340003",
            "extra": "mean: 5.542760001240811 usec\nrounds: 30571"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 19594.53576023152,
            "unit": "iter/sec",
            "range": "stddev: 0.000003169264042091039",
            "extra": "mean: 51.034635994263766 usec\nrounds: 12802"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1972.2410583834278,
            "unit": "iter/sec",
            "range": "stddev: 0.00005663303295043593",
            "extra": "mean: 507.0374109439049 usec\nrounds: 1864"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 206723.20127328802,
            "unit": "iter/sec",
            "range": "stddev: 0.000001374908416437191",
            "extra": "mean: 4.83738638837157 usec\nrounds: 27550"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 3260.1422404737764,
            "unit": "iter/sec",
            "range": "stddev: 0.000008678998067090734",
            "extra": "mean: 306.73508277806803 usec\nrounds: 2404"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 1665.103604202463,
            "unit": "iter/sec",
            "range": "stddev: 0.0000496735882238812",
            "extra": "mean: 600.5632307059784 usec\nrounds: 1192"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 537.4382801571828,
            "unit": "iter/sec",
            "range": "stddev: 0.003003288073604244",
            "extra": "mean: 1.8606787735840722 msec\nrounds: 530"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 47977.328462049256,
            "unit": "iter/sec",
            "range": "stddev: 0.0000025841363659837674",
            "extra": "mean: 20.84317806046692 usec\nrounds: 17831"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_index",
            "value": 29.556560105575326,
            "unit": "iter/sec",
            "range": "stddev: 0.00029588289884397074",
            "extra": "mean: 33.833436517240976 msec\nrounds: 29"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[10]",
            "value": 21614.60501522892,
            "unit": "iter/sec",
            "range": "stddev: 0.000005899973056587602",
            "extra": "mean: 46.265013831871265 usec\nrounds: 9977"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_search[50]",
            "value": 8293.010581820223,
            "unit": "iter/sec",
            "range": "stddev: 0.000009267943180981802",
            "extra": "mean: 120.58347087994564 usec\nrounds: 6044"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 11847.915154681696,
            "unit": "iter/sec",
            "range": "stddev: 0.000009349676273912802",
            "extra": "mean: 84.40303521289572 usec\nrounds: 9258"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3661.213935915185,
            "unit": "iter/sec",
            "range": "stddev: 0.00009855744082092504",
            "extra": "mean: 273.1334517741128 usec\nrounds: 2001"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 2047099.2847522309,
            "unit": "iter/sec",
            "range": "stddev: 7.237927955848985e-8",
            "extra": "mean: 488.4960917374529 nsec\nrounds: 52453"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1892396.8015639458,
            "unit": "iter/sec",
            "range": "stddev: 1.043264034861819e-7",
            "extra": "mean: 528.4304006292779 nsec\nrounds: 178572"
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
          "id": "fdfaf793bfa35b0d59a0a4c08f416efc74e1ecfa",
          "message": "Bump version to 0.14.0 with IVF vector index and reduced dependencies",
          "timestamp": "2026-03-13T16:56:14+09:00",
          "tree_id": "96193d0fead11ebbcc0897ce9fdc49ea4a0346d1",
          "url": "https://github.com/cognica-io/uqa/commit/fdfaf793bfa35b0d59a0a4c08f416efc74e1ecfa"
        },
        "date": 1773388985494,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_simple_select",
            "value": 18190.446910878974,
            "unit": "iter/sec",
            "range": "stddev: 0.000005266969606879343",
            "extra": "mean: 54.97391047615989 usec\nrounds: 3150"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_complex_join",
            "value": 5831.526871260235,
            "unit": "iter/sec",
            "range": "stddev: 0.000012526096242242581",
            "extra": "mean: 171.48167573887778 usec\nrounds: 3417"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_subquery",
            "value": 9105.13016196065,
            "unit": "iter/sec",
            "range": "stddev: 0.000007082656233658862",
            "extra": "mean: 109.828193799776 usec\nrounds: 5774"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_cte",
            "value": 3807.2511068215767,
            "unit": "iter/sec",
            "range": "stddev: 0.000011322713303641472",
            "extra": "mean: 262.6566969035132 usec\nrounds: 2745"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestParse::test_window_function",
            "value": 8748.08003701183,
            "unit": "iter/sec",
            "range": "stddev: 0.000006632838209150898",
            "extra": "mean: 114.31079685704157 usec\nrounds: 5218"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_simple_select",
            "value": 5941.947176029377,
            "unit": "iter/sec",
            "range": "stddev: 0.00006918326596468866",
            "extra": "mean: 168.29500000170583 usec\nrounds: 8"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_multiple_predicates",
            "value": 2580.945436486305,
            "unit": "iter/sec",
            "range": "stddev: 0.000012353050985035757",
            "extra": "mean: 387.45491704830397 usec\nrounds: 1965"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSelect::test_select_with_expressions",
            "value": 4989.184383721928,
            "unit": "iter/sec",
            "range": "stddev: 0.000025691326159844208",
            "extra": "mean: 200.43356250024993 usec\nrounds: 48"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_2way_join",
            "value": 5069.5472756046265,
            "unit": "iter/sec",
            "range": "stddev: 0.000014809323426607182",
            "extra": "mean: 197.2562727271803 usec\nrounds: 209"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileJoin::test_3way_join",
            "value": 3683.4488383677553,
            "unit": "iter/sec",
            "range": "stddev: 0.00025397440148410493",
            "extra": "mean: 271.4846992263722 usec\nrounds: 3102"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by",
            "value": 9262.852486461363,
            "unit": "iter/sec",
            "range": "stddev: 0.000012741574453780689",
            "extra": "mean: 107.95810485610191 usec\nrounds: 5560"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileAggregate::test_group_by_having",
            "value": 7009.398653317218,
            "unit": "iter/sec",
            "range": "stddev: 0.000014425030528351106",
            "extra": "mean: 142.66559079597323 usec\nrounds: 4824"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_scalar_subquery",
            "value": 6033.552984772436,
            "unit": "iter/sec",
            "range": "stddev: 0.000015033064576566044",
            "extra": "mean: 165.7398223772649 usec\nrounds: 3727"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileSubquery::test_exists_subquery",
            "value": 5413.211527651692,
            "unit": "iter/sec",
            "range": "stddev: 0.000015542521122666854",
            "extra": "mean: 184.73322073076466 usec\nrounds: 4023"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_single_cte",
            "value": 3882.7082066382995,
            "unit": "iter/sec",
            "range": "stddev: 0.000013664601209902722",
            "extra": "mean: 257.55218954911203 usec\nrounds: 976"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileCTE::test_multiple_ctes",
            "value": 1405.3833484069178,
            "unit": "iter/sec",
            "range": "stddev: 0.000032711141958328473",
            "extra": "mean: 711.5496288849281 usec\nrounds: 1094"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_row_number",
            "value": 9103.109593057585,
            "unit": "iter/sec",
            "range": "stddev: 0.000009304678311798185",
            "extra": "mean: 109.85257178081675 usec\nrounds: 5677"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileWindow::test_partition_window",
            "value": 7944.63294605036,
            "unit": "iter/sec",
            "range": "stddev: 0.000009739269103234084",
            "extra": "mean: 125.87113926983191 usec\nrounds: 5615"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_insert",
            "value": 4136.293042091536,
            "unit": "iter/sec",
            "range": "stddev: 0.000014430670279839723",
            "extra": "mean: 241.7623678554325 usec\nrounds: 2047"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_update",
            "value": 6506.157724246233,
            "unit": "iter/sec",
            "range": "stddev: 0.00001746754707553958",
            "extra": "mean: 153.70054683324702 usec\nrounds: 4484"
          },
          {
            "name": "benchmarks/bench_compiler.py::TestCompileDML::test_delete",
            "value": 4150.91557555282,
            "unit": "iter/sec",
            "range": "stddev: 0.000014152317726648183",
            "extra": "mean: 240.91070555363433 usec\nrounds: 2863"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_point_lookup",
            "value": 1900.1353922910241,
            "unit": "iter/sec",
            "range": "stddev: 0.000049308892452882784",
            "extra": "mean: 526.278287356294 usec\nrounds: 1044"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_range_scan",
            "value": 1554.6647806287904,
            "unit": "iter/sec",
            "range": "stddev: 0.000035348581784103146",
            "extra": "mean: 643.2254801549861 usec\nrounds: 1033"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_insert_single",
            "value": 1635.6576238214316,
            "unit": "iter/sec",
            "range": "stddev: 0.0004499631381198999",
            "extra": "mean: 611.3748900969097 usec\nrounds: 6806"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_update_where",
            "value": 2093.86637701739,
            "unit": "iter/sec",
            "range": "stddev: 0.000029529458591650397",
            "extra": "mean: 477.58539464416594 usec\nrounds: 1419"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLTP::test_delete_where",
            "value": 1507.9460240998426,
            "unit": "iter/sec",
            "range": "stddev: 0.00003954640255127032",
            "extra": "mean: 663.1537097602301 usec\nrounds: 1168"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_group",
            "value": 92.97779045853076,
            "unit": "iter/sec",
            "range": "stddev: 0.0033494089608166367",
            "extra": "mean: 10.755256659341807 msec\nrounds: 91"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_aggregate_having",
            "value": 93.04777018707232,
            "unit": "iter/sec",
            "range": "stddev: 0.00405143936219208",
            "extra": "mean: 10.74716780412365 msec\nrounds: 97"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_order_by_limit",
            "value": 126.16179922730323,
            "unit": "iter/sec",
            "range": "stddev: 0.003566000566628276",
            "extra": "mean: 7.92632957142851 msec\nrounds: 119"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestOLAP::test_distinct",
            "value": 157.33183784726873,
            "unit": "iter/sec",
            "range": "stddev: 0.0033819479715118494",
            "extra": "mean: 6.355992618421955 msec\nrounds: 152"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_2way_join",
            "value": 155.913887796311,
            "unit": "iter/sec",
            "range": "stddev: 0.0025701151750149244",
            "extra": "mean: 6.413796834483531 msec\nrounds: 145"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_3way_join",
            "value": 110.1571951010044,
            "unit": "iter/sec",
            "range": "stddev: 0.0027000763901869635",
            "extra": "mean: 9.077936298968838 msec\nrounds: 97"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_filter",
            "value": 260.51509880106596,
            "unit": "iter/sec",
            "range": "stddev: 0.0017919010188596999",
            "extra": "mean: 3.838549107526463 msec\nrounds: 186"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestJoin::test_join_with_aggregate",
            "value": 72.91556116042962,
            "unit": "iter/sec",
            "range": "stddev: 0.002192565077112229",
            "extra": "mean: 13.714493642856139 msec\nrounds: 70"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_scalar_subquery",
            "value": 0.10360526788343842,
            "unit": "iter/sec",
            "range": "stddev: 0.037860487979813506",
            "extra": "mean: 9.6520188638 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestSubquery::test_exists_subquery",
            "value": 16.613838065825895,
            "unit": "iter/sec",
            "range": "stddev: 0.0002638840224490473",
            "extra": "mean: 60.19078770588033 msec\nrounds: 17"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_single_cte",
            "value": 52.69195754698386,
            "unit": "iter/sec",
            "range": "stddev: 0.005876616148205209",
            "extra": "mean: 18.97822830188705 msec\nrounds: 53"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestCTE::test_multi_cte",
            "value": 68.84811659033969,
            "unit": "iter/sec",
            "range": "stddev: 0.004773367752869277",
            "extra": "mean: 14.524725577465013 msec\nrounds: 71"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_row_number",
            "value": 159.79569796014775,
            "unit": "iter/sec",
            "range": "stddev: 0.002109550981057215",
            "extra": "mean: 6.257990751724711 msec\nrounds: 145"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestWindowE2E::test_rank_partitioned",
            "value": 138.47247679302623,
            "unit": "iter/sec",
            "range": "stddev: 0.0015260512449294078",
            "extra": "mean: 7.221651718519431 msec\nrounds: 135"
          },
          {
            "name": "benchmarks/bench_e2e.py::TestAnalyze::test_analyze",
            "value": 345.56080407013815,
            "unit": "iter/sec",
            "range": "stddev: 0.000036351267804667146",
            "extra": "mean: 2.8938467216815216 msec\nrounds: 309"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[100]",
            "value": 1804.1310742528672,
            "unit": "iter/sec",
            "range": "stddev: 0.00001673170842577587",
            "extra": "mean: 554.2834521677553 usec\nrounds: 1338"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[500]",
            "value": 444.8482431400694,
            "unit": "iter/sec",
            "range": "stddev: 0.0012342036804441879",
            "extra": "mean: 2.2479576246974857 msec\nrounds: 413"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSeqScan::test_full_scan[1000]",
            "value": 209.64117176920374,
            "unit": "iter/sec",
            "range": "stddev: 0.0034177065585198553",
            "extra": "mean: 4.7700553834955235 msec\nrounds: 206"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_high_selectivity",
            "value": 206.58386754717242,
            "unit": "iter/sec",
            "range": "stddev: 0.0030737277602516893",
            "extra": "mean: 4.840649039410858 msec\nrounds: 203"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_low_selectivity",
            "value": 1700.4018943254312,
            "unit": "iter/sec",
            "range": "stddev: 0.000018418262396074506",
            "extra": "mean: 588.0962632053003 usec\nrounds: 1117"
          },
          {
            "name": "benchmarks/bench_execution.py::TestFilter::test_compound_filter",
            "value": 129.14799831953323,
            "unit": "iter/sec",
            "range": "stddev: 0.005124393586493089",
            "extra": "mean: 7.743054580883528 msec\nrounds: 136"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_simple_project",
            "value": 209.53160794893884,
            "unit": "iter/sec",
            "range": "stddev: 0.003253655176883134",
            "extra": "mean: 4.772549639592762 msec\nrounds: 197"
          },
          {
            "name": "benchmarks/bench_execution.py::TestProject::test_expr_project",
            "value": 71.55043104037676,
            "unit": "iter/sec",
            "range": "stddev: 0.004159304015815756",
            "extra": "mean: 13.976156194442602 msec\nrounds: 72"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_single_column",
            "value": 56.98156073331497,
            "unit": "iter/sec",
            "range": "stddev: 0.005837291337055478",
            "extra": "mean: 17.54953685246002 msec\nrounds: 61"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_multi_column",
            "value": 81.03295894056954,
            "unit": "iter/sec",
            "range": "stddev: 0.004481005483250908",
            "extra": "mean: 12.340657592590329 msec\nrounds: 81"
          },
          {
            "name": "benchmarks/bench_execution.py::TestSort::test_sort_with_limit",
            "value": 59.02997424032266,
            "unit": "iter/sec",
            "range": "stddev: 0.004157958558161359",
            "extra": "mean: 16.940546101694082 msec\nrounds: 59"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_count_group_by",
            "value": 99.35001247835943,
            "unit": "iter/sec",
            "range": "stddev: 0.0034983796691078948",
            "extra": "mean: 10.065424000000217 msec\nrounds: 98"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_sum_avg_group_by",
            "value": 94.70482737118643,
            "unit": "iter/sec",
            "range": "stddev: 0.003248353419171622",
            "extra": "mean: 10.55912383516203 msec\nrounds: 91"
          },
          {
            "name": "benchmarks/bench_execution.py::TestHashAggregate::test_high_cardinality_group",
            "value": 80.33004740079531,
            "unit": "iter/sec",
            "range": "stddev: 0.005629789168446577",
            "extra": "mean: 12.448641975905264 msec\nrounds: 83"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_low_cardinality",
            "value": 160.79519502211028,
            "unit": "iter/sec",
            "range": "stddev: 0.002912517595374875",
            "extra": "mean: 6.219091309678092 msec\nrounds: 155"
          },
          {
            "name": "benchmarks/bench_execution.py::TestDistinct::test_high_cardinality",
            "value": 155.65925769355286,
            "unit": "iter/sec",
            "range": "stddev: 0.0026062898990985837",
            "extra": "mean: 6.424288634144105 msec\nrounds: 41"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_row_number",
            "value": 162.2484449406566,
            "unit": "iter/sec",
            "range": "stddev: 0.0013729731826345884",
            "extra": "mean: 6.163387269232419 msec\nrounds: 156"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_rank_partitioned",
            "value": 137.93982887105895,
            "unit": "iter/sec",
            "range": "stddev: 0.0020292783733978285",
            "extra": "mean: 7.249537774436149 msec\nrounds: 133"
          },
          {
            "name": "benchmarks/bench_execution.py::TestWindow::test_sum_window",
            "value": 42.831930979066044,
            "unit": "iter/sec",
            "range": "stddev: 0.00027923374893475014",
            "extra": "mean: 23.347067880006307 msec\nrounds: 25"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[10]",
            "value": 211.3187880197889,
            "unit": "iter/sec",
            "range": "stddev: 0.003076121118275888",
            "extra": "mean: 4.732186898149138 msec\nrounds: 216"
          },
          {
            "name": "benchmarks/bench_execution.py::TestLimit::test_limit[100]",
            "value": 218.7210298713676,
            "unit": "iter/sec",
            "range": "stddev: 0.0027905733794651405",
            "extra": "mean: 4.572034068183164 msec\nrounds: 44"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_filter_project_sort_limit",
            "value": 73.21630718595712,
            "unit": "iter/sec",
            "range": "stddev: 0.0055302875080119164",
            "extra": "mean: 13.658159478873579 msec\nrounds: 71"
          },
          {
            "name": "benchmarks/bench_execution.py::TestPipeline::test_scan_group_sort",
            "value": 79.67209220983337,
            "unit": "iter/sec",
            "range": "stddev: 0.004411906879945547",
            "extra": "mean: 12.551446463415164 msec\nrounds: 82"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[1]",
            "value": 630259.626776799,
            "unit": "iter/sec",
            "range": "stddev: 3.345656843274212e-7",
            "extra": "mean: 1.5866477202642417 usec\nrounds: 60205"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[2]",
            "value": 260892.80372408757,
            "unit": "iter/sec",
            "range": "stddev: 5.447977898826942e-7",
            "extra": "mean: 3.8329918868040918 usec\nrounds: 40674"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_depth[3]",
            "value": 77699.18660019051,
            "unit": "iter/sec",
            "range": "stddev: 0.000001072366729866321",
            "extra": "mean: 12.870147600715656 usec\nrounds: 30779"
          },
          {
            "name": "benchmarks/bench_graph.py::TestBFSTraversal::test_bfs_with_label",
            "value": 769468.5742727711,
            "unit": "iter/sec",
            "range": "stddev: 3.321906926808375e-7",
            "extra": "mean: 1.2995982336836893 usec\nrounds: 107794"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_out_neighbors",
            "value": 2159178.2243318395,
            "unit": "iter/sec",
            "range": "stddev: 4.445125497424167e-8",
            "extra": "mean: 463.13916504481756 nsec\nrounds: 107910"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_in_neighbors",
            "value": 1691757.3171109138,
            "unit": "iter/sec",
            "range": "stddev: 5.247019072838345e-8",
            "extra": "mean: 591.1013298927193 nsec\nrounds: 80232"
          },
          {
            "name": "benchmarks/bench_graph.py::TestNeighbors::test_labeled_neighbors",
            "value": 2461195.729251933,
            "unit": "iter/sec",
            "range": "stddev: 4.439517966043138e-8",
            "extra": "mean: 406.306572092072 nsec\nrounds: 119977"
          },
          {
            "name": "benchmarks/bench_graph.py::TestVertexLookup::test_vertices_by_label",
            "value": 174842.79159733892,
            "unit": "iter/sec",
            "range": "stddev: 7.60089841302408e-7",
            "extra": "mean: 5.719423665477667 usec\nrounds: 89920"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_single_edge_pattern",
            "value": 1599.9402901409487,
            "unit": "iter/sec",
            "range": "stddev: 0.000025939156151149818",
            "extra": "mean: 625.023325034151 usec\nrounds: 723"
          },
          {
            "name": "benchmarks/bench_graph.py::TestPatternMatch::test_labeled_edge_pattern",
            "value": 1610.8501369954556,
            "unit": "iter/sec",
            "range": "stddev: 0.0000138935375787913",
            "extra": "mean: 620.7902132132489 usec\nrounds: 1332"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_simple",
            "value": 435813.7892335671,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010299045158164746",
            "extra": "mean: 2.294557961919068 usec\nrounds: 65198"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_concat",
            "value": 191080.95693660868,
            "unit": "iter/sec",
            "range": "stddev: 8.143973096477215e-7",
            "extra": "mean: 5.233383881009927 usec\nrounds: 60972"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_alternation",
            "value": 117544.10685679263,
            "unit": "iter/sec",
            "range": "stddev: 9.708054656921721e-7",
            "extra": "mean: 8.507444794474713 usec\nrounds: 47622"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_kleene",
            "value": 335889.29499163094,
            "unit": "iter/sec",
            "range": "stddev: 6.09737875664634e-7",
            "extra": "mean: 2.977171392213962 usec\nrounds: 98155"
          },
          {
            "name": "benchmarks/bench_graph.py::TestRPQ::test_parse_complex",
            "value": 102029.5484366473,
            "unit": "iter/sec",
            "range": "stddev: 0.000001017102805471733",
            "extra": "mean: 9.801082287656355 usec\nrounds: 47735"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_simple_match",
            "value": 15502.739033340466,
            "unit": "iter/sec",
            "range": "stddev: 0.0000038962363688676055",
            "extra": "mean: 64.50473028342812 usec\nrounds: 5465"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_multi_hop",
            "value": 9994.983582406217,
            "unit": "iter/sec",
            "range": "stddev: 0.000005426880719708524",
            "extra": "mean: 100.05018935301318 usec\nrounds: 7589"
          },
          {
            "name": "benchmarks/bench_graph.py::TestCypherCompile::test_filtered",
            "value": 12120.399973505318,
            "unit": "iter/sec",
            "range": "stddev: 0.000004374504338192272",
            "extra": "mean: 82.5055280507209 usec\nrounds: 7736"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[3]",
            "value": 90596.96479603538,
            "unit": "iter/sec",
            "range": "stddev: 0.0000010916070284203553",
            "extra": "mean: 11.037897376047207 usec\nrounds: 19284"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[5]",
            "value": 25971.104517044118,
            "unit": "iter/sec",
            "range": "stddev: 0.000001894740619260265",
            "extra": "mean: 38.5043308167247 usec\nrounds: 2252"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[8]",
            "value": 6020.9510584515165,
            "unit": "iter/sec",
            "range": "stddev: 0.000006124208325388294",
            "extra": "mean: 166.08671791083825 usec\nrounds: 4020"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_chain[10]",
            "value": 2114.24363768151,
            "unit": "iter/sec",
            "range": "stddev: 0.000015144700543377964",
            "extra": "mean: 472.9823858411158 usec\nrounds: 1568"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[3]",
            "value": 90128.26057276655,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011325977215828273",
            "extra": "mean: 11.095299006604408 usec\nrounds: 35434"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[5]",
            "value": 18087.30968947261,
            "unit": "iter/sec",
            "range": "stddev: 0.0000025258637015117288",
            "extra": "mean: 55.287381991476146 usec\nrounds: 11228"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[8]",
            "value": 1318.9357176893122,
            "unit": "iter/sec",
            "range": "stddev: 0.00000815861114128031",
            "extra": "mean: 758.1870644552213 usec\nrounds: 1055"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[10]",
            "value": 181.37532770394276,
            "unit": "iter/sec",
            "range": "stddev: 0.000030989473831877026",
            "extra": "mean: 5.51342904605135 msec\nrounds: 152"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_star[16]",
            "value": 0.38796359089230903,
            "unit": "iter/sec",
            "range": "stddev: 0.08042886292820546",
            "extra": "mean: 2.5775614605999975 sec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[3]",
            "value": 71720.66516625311,
            "unit": "iter/sec",
            "range": "stddev: 0.0000013716334972775051",
            "extra": "mean: 13.942982788599853 usec\nrounds: 25913"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[5]",
            "value": 6394.614887847508,
            "unit": "iter/sec",
            "range": "stddev: 0.000014624899650252284",
            "extra": "mean: 156.38158318187794 usec\nrounds: 4947"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_clique[8]",
            "value": 158.5638833383146,
            "unit": "iter/sec",
            "range": "stddev: 0.00003883252689677138",
            "extra": "mean: 6.306606390727596 msec\nrounds: 151"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[3]",
            "value": 71520.20437294812,
            "unit": "iter/sec",
            "range": "stddev: 0.0000018612735211090077",
            "extra": "mean: 13.982062953643362 usec\nrounds: 30038"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[5]",
            "value": 14821.552187176118,
            "unit": "iter/sec",
            "range": "stddev: 0.000003451557950656383",
            "extra": "mean: 67.46931680105803 usec\nrounds: 8690"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[8]",
            "value": 2698.3876427478317,
            "unit": "iter/sec",
            "range": "stddev: 0.000007624350462128894",
            "extra": "mean: 370.5916763618427 usec\nrounds: 1891"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccp::test_cycle[10]",
            "value": 779.847217116959,
            "unit": "iter/sec",
            "range": "stddev: 0.000021265522943554847",
            "extra": "mean: 1.2823024536741063 msec\nrounds: 626"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_chain_8",
            "value": 6134.622416589311,
            "unit": "iter/sec",
            "range": "stddev: 0.000005250561914487601",
            "extra": "mean: 163.0092175348542 usec\nrounds: 4243"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_star_8",
            "value": 1325.792538660774,
            "unit": "iter/sec",
            "range": "stddev: 0.00001471613797410932",
            "extra": "mean: 754.2658227735483 usec\nrounds: 1089"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_clique_8",
            "value": 156.7963054007655,
            "unit": "iter/sec",
            "range": "stddev: 0.000028633020756421997",
            "extra": "mean: 6.377701294963789 msec\nrounds: 139"
          },
          {
            "name": "benchmarks/bench_planner.py::TestDPccpTopology::test_cycle_8",
            "value": 2697.9211250472113,
            "unit": "iter/sec",
            "range": "stddev: 0.000007774630447826802",
            "extra": "mean: 370.6557581376664 usec\nrounds: 1997"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[16]",
            "value": 52.42463233978273,
            "unit": "iter/sec",
            "range": "stddev: 0.0003473246167840609",
            "extra": "mean: 19.075002634613504 msec\nrounds: 52"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[20]",
            "value": 1214.4853141365681,
            "unit": "iter/sec",
            "range": "stddev: 0.000009543790699962018",
            "extra": "mean: 823.3940652554902 usec\nrounds: 1134"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_chain[30]",
            "value": 392.5959503423005,
            "unit": "iter/sec",
            "range": "stddev: 0.000021184191684655733",
            "extra": "mean: 2.547148026178339 msec\nrounds: 382"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[20]",
            "value": 1429.5057187426128,
            "unit": "iter/sec",
            "range": "stddev: 0.000010924768845105346",
            "extra": "mean: 699.5424970244931 usec\nrounds: 1344"
          },
          {
            "name": "benchmarks/bench_planner.py::TestGreedyFallback::test_greedy_star[30]",
            "value": 468.6702720783365,
            "unit": "iter/sec",
            "range": "stddev: 0.000017169174979837563",
            "extra": "mean: 2.1336962456898774 msec\nrounds: 464"
          },
          {
            "name": "benchmarks/bench_planner.py::TestHistogram::test_analyze",
            "value": 350.05888250124644,
            "unit": "iter/sec",
            "range": "stddev: 0.00002977985555829176",
            "extra": "mean: 2.85666226451614 msec\nrounds: 310"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_equality_selectivity",
            "value": 1713.9115165489243,
            "unit": "iter/sec",
            "range": "stddev: 0.00003188609104531363",
            "extra": "mean: 583.460692307831 usec\nrounds: 871"
          },
          {
            "name": "benchmarks/bench_planner.py::TestSelectivity::test_range_selectivity",
            "value": 1326.9615023243214,
            "unit": "iter/sec",
            "range": "stddev: 0.00002174590173652056",
            "extra": "mean: 753.6013654114216 usec\nrounds: 717"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[1000]",
            "value": 858.9194448612201,
            "unit": "iter/sec",
            "range": "stddev: 0.001340035353040867",
            "extra": "mean: 1.1642535350466714 msec\nrounds: 856"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[10000]",
            "value": 64.56804904715331,
            "unit": "iter/sec",
            "range": "stddev: 0.011603841678757679",
            "extra": "mean: 15.487536246754358 msec\nrounds: 77"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_size[100000]",
            "value": 5.9063893470074875,
            "unit": "iter/sec",
            "range": "stddev: 0.0461368216054684",
            "extra": "mean: 169.30817479999973 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.0]",
            "value": 267.99326773861634,
            "unit": "iter/sec",
            "range": "stddev: 0.00004597390948443687",
            "extra": "mean: 3.7314370186915915 msec\nrounds: 214"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.3]",
            "value": 66.74703105941555,
            "unit": "iter/sec",
            "range": "stddev: 0.011533747166550071",
            "extra": "mean: 14.981939782607558 msec\nrounds: 23"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[0.7]",
            "value": 31.85509378744453,
            "unit": "iter/sec",
            "range": "stddev: 0.015290191865139309",
            "extra": "mean: 31.392153690476444 msec\nrounds: 42"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestUnion::test_union_by_overlap[1.0]",
            "value": 23.596507310200206,
            "unit": "iter/sec",
            "range": "stddev: 0.016786401599316415",
            "extra": "mean: 42.3791532727271 msec\nrounds: 33"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[1000]",
            "value": 866.5299497156685,
            "unit": "iter/sec",
            "range": "stddev: 0.0012729514892977612",
            "extra": "mean: 1.1540282021736543 msec\nrounds: 920"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[10000]",
            "value": 64.30630345347679,
            "unit": "iter/sec",
            "range": "stddev: 0.011430976926255484",
            "extra": "mean: 15.550575080457902 msec\nrounds: 87"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_size[100000]",
            "value": 5.812773616990565,
            "unit": "iter/sec",
            "range": "stddev: 0.044294761266209993",
            "extra": "mean: 172.03491239999948 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.0]",
            "value": 265.3031116469225,
            "unit": "iter/sec",
            "range": "stddev: 0.0000577377623310974",
            "extra": "mean: 3.7692735444838874 msec\nrounds: 281"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.3]",
            "value": 67.56736796567316,
            "unit": "iter/sec",
            "range": "stddev: 0.010445841529857669",
            "extra": "mean: 14.800043720928109 msec\nrounds: 86"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[0.7]",
            "value": 30.288997631101,
            "unit": "iter/sec",
            "range": "stddev: 0.016078026854871936",
            "extra": "mean: 33.01528865957557 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestIntersect::test_intersect_by_overlap[1.0]",
            "value": 22.955308215743287,
            "unit": "iter/sec",
            "range": "stddev: 0.0172217123557194",
            "extra": "mean: 43.56290887500158 msec\nrounds: 16"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[1000]",
            "value": 15846.227420171637,
            "unit": "iter/sec",
            "range": "stddev: 0.000003730268502620534",
            "extra": "mean: 63.10650311171469 usec\nrounds: 10284"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[10000]",
            "value": 963.0699209969932,
            "unit": "iter/sec",
            "range": "stddev: 0.000026280170075380038",
            "extra": "mean: 1.038346207474506 msec\nrounds: 776"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_size[100000]",
            "value": 69.74010498159006,
            "unit": "iter/sec",
            "range": "stddev: 0.0013986178415293063",
            "extra": "mean: 14.3389517446809 msec\nrounds: 47"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.0]",
            "value": 1085.4382994346527,
            "unit": "iter/sec",
            "range": "stddev: 0.00001522685622295438",
            "extra": "mean: 921.286820744069 usec\nrounds: 887"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.3]",
            "value": 971.1462801895739,
            "unit": "iter/sec",
            "range": "stddev: 0.000021660067839641998",
            "extra": "mean: 1.0297109924622208 msec\nrounds: 796"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[0.7]",
            "value": 905.4358147937601,
            "unit": "iter/sec",
            "range": "stddev: 0.000027599461809672898",
            "extra": "mean: 1.104440517661409 msec\nrounds: 821"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestDifference::test_difference_by_overlap[1.0]",
            "value": 896.4119848739305,
            "unit": "iter/sec",
            "range": "stddev: 0.000027115004451719575",
            "extra": "mean: 1.1155584897056434 msec\nrounds: 680"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[10]",
            "value": 113.53228774691947,
            "unit": "iter/sec",
            "range": "stddev: 0.0009459368954183551",
            "extra": "mean: 8.808067025207405 msec\nrounds: 119"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[100]",
            "value": 158.96016506073175,
            "unit": "iter/sec",
            "range": "stddev: 0.0004638189800423284",
            "extra": "mean: 6.290884257813545 msec\nrounds: 128"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestTopK::test_top_k[1000]",
            "value": 99.31562096329239,
            "unit": "iter/sec",
            "range": "stddev: 0.0007015593539898468",
            "extra": "mean: 10.068909505883326 msec\nrounds: 85"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[2]",
            "value": 59.79831166400194,
            "unit": "iter/sec",
            "range": "stddev: 0.012062947889761958",
            "extra": "mean: 16.722880164558077 msec\nrounds: 79"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[4]",
            "value": 16.93177038211799,
            "unit": "iter/sec",
            "range": "stddev: 0.021122806299627834",
            "extra": "mean: 59.06056941665838 msec\nrounds: 12"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[8]",
            "value": 6.281099805752416,
            "unit": "iter/sec",
            "range": "stddev: 0.027118864923214785",
            "extra": "mean: 159.20778700000446 msec\nrounds: 6"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_union[16]",
            "value": 2.3523102768914765,
            "unit": "iter/sec",
            "range": "stddev: 0.010424277642285287",
            "extra": "mean: 425.1139868000223 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[2]",
            "value": 41.86636810865325,
            "unit": "iter/sec",
            "range": "stddev: 0.0144464310184698",
            "extra": "mean: 23.885520650006242 msec\nrounds: 20"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[4]",
            "value": 13.849073693814708,
            "unit": "iter/sec",
            "range": "stddev: 0.021779255173548975",
            "extra": "mean: 72.20699536364091 msec\nrounds: 11"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[8]",
            "value": 6.094315774755915,
            "unit": "iter/sec",
            "range": "stddev: 0.001956671697678434",
            "extra": "mean: 164.08732940000164 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestMultiMerge::test_nway_intersect[16]",
            "value": 2.946267754716866,
            "unit": "iter/sec",
            "range": "stddev: 0.03943978750534678",
            "extra": "mean: 339.41246460001366 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_union_with_scores",
            "value": 43.445442222984155,
            "unit": "iter/sec",
            "range": "stddev: 0.01384166227384652",
            "extra": "mean: 23.017374178572986 msec\nrounds: 56"
          },
          {
            "name": "benchmarks/bench_posting_list.py::TestPayloadMerge::test_get_entry_binary_search",
            "value": 445287.589696233,
            "unit": "iter/sec",
            "range": "stddev: 4.2135291506658286e-7",
            "extra": "mean: 2.245739659356286 usec\nrounds: 83529"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_single",
            "value": 1379636.2733294275,
            "unit": "iter/sec",
            "range": "stddev: 2.3454997663904788e-7",
            "extra": "mean: 724.8287243033523 nsec\nrounds: 97381"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_score_batch",
            "value": 120.12051802908275,
            "unit": "iter/sec",
            "range": "stddev: 0.0000716198622286715",
            "extra": "mean: 8.324972422762004 msec\nrounds: 123"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_idf",
            "value": 3317567.9146314254,
            "unit": "iter/sec",
            "range": "stddev: 3.9606196144771576e-8",
            "extra": "mean: 301.42563038113354 nsec\nrounds: 196503"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[1]",
            "value": 4348919.91288359,
            "unit": "iter/sec",
            "range": "stddev: 2.9218360812696673e-8",
            "extra": "mean: 229.9421511620666 nsec\nrounds: 197668"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[3]",
            "value": 4075381.2588446327,
            "unit": "iter/sec",
            "range": "stddev: 3.0265277589037815e-8",
            "extra": "mean: 245.37581553375918 nsec\nrounds: 192679"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[5]",
            "value": 3930106.734417301,
            "unit": "iter/sec",
            "range": "stddev: 3.284522976187021e-8",
            "extra": "mean: 254.4460157386197 nsec\nrounds: 194553"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBM25::test_combine_scores[10]",
            "value": 3438804.0163522884,
            "unit": "iter/sec",
            "range": "stddev: 3.5844701645157026e-8",
            "extra": "mean: 290.79877633176375 nsec\nrounds: 189394"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_single",
            "value": 29868.424045271408,
            "unit": "iter/sec",
            "range": "stddev: 0.00000316855531376201",
            "extra": "mean: 33.48017285693766 usec\nrounds: 4981"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_score_batch",
            "value": 30.105548276027125,
            "unit": "iter/sec",
            "range": "stddev: 0.0008676916419667496",
            "extra": "mean: 33.21646863333474 msec\nrounds: 30"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[1]",
            "value": 6592322.694631261,
            "unit": "iter/sec",
            "range": "stddev: 1.1584948231178185e-8",
            "extra": "mean: 151.69160344871963 nsec\nrounds: 65540"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[3]",
            "value": 32888.62344648961,
            "unit": "iter/sec",
            "range": "stddev: 0.000003564496816788493",
            "extra": "mean: 30.40565080587876 usec\nrounds: 11412"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[5]",
            "value": 32775.15098004027,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034902149220493043",
            "extra": "mean: 30.510919708927954 usec\nrounds: 18844"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestBayesianBM25::test_combine_scores[10]",
            "value": 32298.536349888083,
            "unit": "iter/sec",
            "range": "stddev: 0.000004421476662811093",
            "extra": "mean: 30.961155303356808 usec\nrounds: 12614"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[64]",
            "value": 219746.02117665976,
            "unit": "iter/sec",
            "range": "stddev: 7.463496742494703e-7",
            "extra": "mean: 4.550708106774198 usec\nrounds: 68227"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[128]",
            "value": 219366.51790368,
            "unit": "iter/sec",
            "range": "stddev: 7.678637617811358e-7",
            "extra": "mean: 4.558580815140998 usec\nrounds: 114601"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_similarity[256]",
            "value": 219509.39173672034,
            "unit": "iter/sec",
            "range": "stddev: 7.808025772663249e-7",
            "extra": "mean: 4.555613735194531 usec\nrounds: 118134"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_similarity_to_probability",
            "value": 186610.79200970742,
            "unit": "iter/sec",
            "range": "stddev: 8.613107016086232e-7",
            "extra": "mean: 5.35874688291329 usec\nrounds: 22618"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestVectorScoring::test_cosine_batch",
            "value": 226.74853887526783,
            "unit": "iter/sec",
            "range": "stddev: 0.000039172666091858194",
            "extra": "mean: 4.4101717477883735 msec\nrounds: 226"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[2]",
            "value": 32758.798029227077,
            "unit": "iter/sec",
            "range": "stddev: 0.000004015478825183678",
            "extra": "mean: 30.526150535432034 usec\nrounds: 9247"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[3]",
            "value": 32986.76056836203,
            "unit": "iter/sec",
            "range": "stddev: 0.000003618262087642617",
            "extra": "mean: 30.315192603638422 usec\nrounds: 15197"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[5]",
            "value": 32903.618862848896,
            "unit": "iter/sec",
            "range": "stddev: 0.0000037634315022643416",
            "extra": "mean: 30.391793807491755 usec\nrounds: 15277"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse[10]",
            "value": 32349.41496293248,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034978122898408274",
            "extra": "mean: 30.91246012163893 usec\nrounds: 11999"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_batch",
            "value": 3.4170832439113568,
            "unit": "iter/sec",
            "range": "stddev: 0.000950068628307081",
            "extra": "mean: 292.6472458000035 msec\nrounds: 5"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[2]",
            "value": 26789.273206777212,
            "unit": "iter/sec",
            "range": "stddev: 0.000004162573160160577",
            "extra": "mean: 37.328373647218534 usec\nrounds: 9608"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[3]",
            "value": 26346.23798670917,
            "unit": "iter/sec",
            "range": "stddev: 0.0000063946028186027",
            "extra": "mean: 37.95608316088498 usec\nrounds: 10161"
          },
          {
            "name": "benchmarks/bench_scoring.py::TestLogOddsFusion::test_fuse_weighted[5]",
            "value": 26502.18635209903,
            "unit": "iter/sec",
            "range": "stddev: 0.00000397625415977682",
            "extra": "mean: 37.73273596051059 usec\nrounds: 13373"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_single",
            "value": 172191.0922842646,
            "unit": "iter/sec",
            "range": "stddev: 0.0000011180368430556137",
            "extra": "mean: 5.807501344779979 usec\nrounds: 31972"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[10]",
            "value": 19396.176280987995,
            "unit": "iter/sec",
            "range": "stddev: 0.000003440370686767139",
            "extra": "mean: 51.55655349349415 usec\nrounds: 10347"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_put_batch[100]",
            "value": 1928.2576139036507,
            "unit": "iter/sec",
            "range": "stddev: 0.000011469524366210619",
            "extra": "mean: 518.602904917645 usec\nrounds: 1830"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_get_random",
            "value": 204684.64180809856,
            "unit": "iter/sec",
            "range": "stddev: 9.141200772925967e-7",
            "extra": "mean: 4.885564403691542 usec\nrounds: 26660"
          },
          {
            "name": "benchmarks/bench_storage.py::TestDocumentStore::test_scan_all",
            "value": 3255.977935876933,
            "unit": "iter/sec",
            "range": "stddev: 0.000010238569086562077",
            "extra": "mean: 307.12738835887404 usec\nrounds: 2302"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_add_document",
            "value": 1687.674680358693,
            "unit": "iter/sec",
            "range": "stddev: 0.00004217209578303184",
            "extra": "mean: 592.5312571422019 usec\nrounds: 1190"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_get_posting_list",
            "value": 609.34181211453,
            "unit": "iter/sec",
            "range": "stddev: 0.00002504702696272947",
            "extra": "mean: 1.641115019712521 msec\nrounds: 558"
          },
          {
            "name": "benchmarks/bench_storage.py::TestInvertedIndex::test_doc_freq",
            "value": 48863.25101768064,
            "unit": "iter/sec",
            "range": "stddev: 0.000001803091182153196",
            "extra": "mean: 20.46527767131501 usec\nrounds: 15151"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_build_500",
            "value": 59.56346910333708,
            "unit": "iter/sec",
            "range": "stddev: 0.0025160033957084514",
            "extra": "mean: 16.78881393333711 msec\nrounds: 60"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_add_single",
            "value": 42161.72159647987,
            "unit": "iter/sec",
            "range": "stddev: 0.00005142216259129759",
            "extra": "mean: 23.71819655683821 usec\nrounds: 21027"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_brute_force[10]",
            "value": 2023.977156179974,
            "unit": "iter/sec",
            "range": "stddev: 0.000016311646737432943",
            "extra": "mean: 494.07672262832546 usec\nrounds: 1644"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_brute_force[50]",
            "value": 1806.268478745085,
            "unit": "iter/sec",
            "range": "stddev: 0.000012312930385306013",
            "extra": "mean: 553.6275541356706 usec\nrounds: 1644"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_trained[10]",
            "value": 2636.801937113673,
            "unit": "iter/sec",
            "range": "stddev: 0.000016133950463899174",
            "extra": "mean: 379.2472942031557 usec\nrounds: 2070"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_knn_trained[50]",
            "value": 2273.2759634656013,
            "unit": "iter/sec",
            "range": "stddev: 0.00001352966708255474",
            "extra": "mean: 439.89379911249466 usec\nrounds: 2026"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_threshold_search",
            "value": 2968.8833407494103,
            "unit": "iter/sec",
            "range": "stddev: 0.000014193444535289717",
            "extra": "mean: 336.82697675402034 usec\nrounds: 2538"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_delete",
            "value": 308995.1279547115,
            "unit": "iter/sec",
            "range": "stddev: 0.0000058621235402378075",
            "extra": "mean: 3.236296981829976 usec\nrounds: 11728"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_train",
            "value": 5.3556719409711055,
            "unit": "iter/sec",
            "range": "stddev: 0.0004737874309239967",
            "extra": "mean: 186.71793400001965 msec\nrounds: 6"
          },
          {
            "name": "benchmarks/bench_storage.py::TestVectorIndex::test_persistence_roundtrip",
            "value": 4056.1106891596137,
            "unit": "iter/sec",
            "range": "stddev: 0.000015468292165075294",
            "extra": "mean: 246.54159529536662 usec\nrounds: 2508"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_vertices",
            "value": 12035.665786764668,
            "unit": "iter/sec",
            "range": "stddev: 0.000003661510365250317",
            "extra": "mean: 83.0863882162361 usec\nrounds: 9420"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_add_edges",
            "value": 3516.967815937148,
            "unit": "iter/sec",
            "range": "stddev: 0.00010739157433060891",
            "extra": "mean: 284.33584051252836 usec\nrounds: 1950"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors",
            "value": 2017400.7663623542,
            "unit": "iter/sec",
            "range": "stddev: 6.332658455159898e-8",
            "extra": "mean: 495.6873302884359 nsec\nrounds: 193051"
          },
          {
            "name": "benchmarks/bench_storage.py::TestGraphStore::test_neighbors_with_label",
            "value": 1877436.2014983804,
            "unit": "iter/sec",
            "range": "stddev: 6.707665809925021e-8",
            "extra": "mean: 532.6412685565031 nsec\nrounds: 184809"
          }
        ]
      }
    ]
  }
}