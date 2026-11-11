// Immediate assertions wrapping tile_top. Bound/proved by SymbiYosys (O8).
// Yosys 0.70 `read -formal` does not parse `bind`; use a wrapper top.
// Tiny instance (R=1,C=1,K_MAX=2) keeps z3 tractable.
`default_nettype none

module tile_formal (
    input  logic              clk,
    input  logic              rst_n,
    input  logic [15:0]       cfg_k_i,
    input  logic              start_i,
    output logic              busy_o,
    output logic              done_o,
    output logic              err_o,
    output logic [2:0]        err_code_o,
    input  logic signed [7:0] s_axis_a_tdata,
    input  logic              s_axis_a_tvalid,
    output logic              s_axis_a_tready,
    input  logic              s_axis_a_tlast,
    input  logic signed [7:0] s_axis_b_tdata,
    input  logic              s_axis_b_tvalid,
    output logic              s_axis_b_tready,
    input  logic              s_axis_b_tlast,
    output logic signed [31:0] m_axis_c_tdata,
    output logic              m_axis_c_tvalid,
    input  logic              m_axis_c_tready,
    output logic              m_axis_c_tlast
);
    localparam int R = 1;
    localparam int C = 1;
    localparam int K_MAX = 2;

    tile_top #(.R(R), .C(C), .K_MAX(K_MAX)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .cfg_k_i(cfg_k_i),
        .start_i(start_i),
        .busy_o(busy_o),
        .done_o(done_o),
        .err_o(err_o),
        .err_code_o(err_code_o),
        .s_axis_a_tdata(s_axis_a_tdata),
        .s_axis_a_tvalid(s_axis_a_tvalid),
        .s_axis_a_tready(s_axis_a_tready),
        .s_axis_a_tlast(s_axis_a_tlast),
        .s_axis_b_tdata(s_axis_b_tdata),
        .s_axis_b_tvalid(s_axis_b_tvalid),
        .s_axis_b_tready(s_axis_b_tready),
        .s_axis_b_tlast(s_axis_b_tlast),
        .m_axis_c_tdata(m_axis_c_tdata),
        .m_axis_c_tvalid(m_axis_c_tvalid),
        .m_axis_c_tready(m_axis_c_tready),
        .m_axis_c_tlast(m_axis_c_tlast)
    );

    logic seen = 1'b0;
    logic inited = 1'b0;
    logic rst_d = 1'b0;
    logic busy_d, start_d, done_d;
    logic k_ok_d;
    logic [15:0] cfg_d, k_latched;
    logic a_v_d, a_r_d, b_v_d, b_r_d, c_v_d, c_r_d, c_l_d;
    logic signed [31:0] c_d_d;
    logic [15:0] a_beats, b_beats, c_beats;

    wire k_ok = (cfg_k_i >= 16'd1) && (cfg_k_i <= K_MAX[15:0]);
    wire [15:0] a_n = a_beats + ((a_v_d && a_r_d) ? 16'd1 : 16'd0);
    wire [15:0] b_n = b_beats + ((b_v_d && b_r_d) ? 16'd1 : 16'd0);
    wire [15:0] c_n = c_beats + ((c_v_d && c_r_d) ? 16'd1 : 16'd0);
    wire accepted_d = rst_d && !busy_d && start_d && k_ok_d;

    always_ff @(posedge clk) begin
        seen    <= 1'b1;
        if (!rst_n)
            inited <= 1'b1;
        rst_d   <= rst_n;
        busy_d  <= busy_o;
        start_d <= start_i;
        done_d  <= done_o;
        k_ok_d  <= k_ok;
        cfg_d   <= cfg_k_i;
        a_v_d   <= s_axis_a_tvalid;
        a_r_d   <= s_axis_a_tready;
        b_v_d   <= s_axis_b_tvalid;
        b_r_d   <= s_axis_b_tready;
        c_v_d   <= m_axis_c_tvalid;
        c_r_d   <= m_axis_c_tready;
        c_d_d   <= m_axis_c_tdata;
        c_l_d   <= m_axis_c_tlast;

        if (!rst_n) begin
            a_beats   <= 16'd0;
            b_beats   <= 16'd0;
            c_beats   <= 16'd0;
            k_latched <= 16'd1;
        end else if (accepted_d) begin
            a_beats   <= 16'd0;
            b_beats   <= 16'd0;
            c_beats   <= 16'd0;
            k_latched <= cfg_d;
        end else begin
            a_beats <= a_n;
            b_beats <= b_n;
            c_beats <= c_n;
        end

        if (seen && !rst_d && !rst_n) begin
            assert (!busy_o);
            assert (!done_o);
            assert (err_code_o == 3'b000);
            assert (!s_axis_a_tready);
            assert (!s_axis_b_tready);
            assert (!m_axis_c_tvalid);
        end

        if (seen && inited && rst_d && rst_n) begin
            if (c_v_d && !c_r_d) begin
                assert (m_axis_c_tvalid);
                assert (m_axis_c_tdata == c_d_d);
                assert (m_axis_c_tlast == c_l_d);
            end
            if (done_o) begin
                assert (!m_axis_c_tvalid);
                assert (!busy_o);
                assert (a_n == (R[15:0] * k_latched));
                assert (b_n == (k_latched * C[15:0]));
                assert (c_n == (R[15:0] * C[15:0]));
            end
            if (busy_d && !done_o)
                assert (busy_o);
            if (accepted_d) begin
                assert (err_code_o == 3'b000);
                assert (busy_o);
            end
            assert (err_o == |err_code_o);
        end

        cover (inited && rst_d && done_o);
        cover (inited && rst_d && m_axis_c_tvalid && !m_axis_c_tready);
        cover (inited && rst_d && err_code_o[0]);
        cover (inited && rst_d && rst_n && !busy_o && !done_o);
    end
endmodule

`default_nettype wire
