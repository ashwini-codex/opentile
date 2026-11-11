// tile_top: scratchpad, AXI-Stream A/B/C, IDLE/LOAD/COMPUTE/DRAIN/STORE, O7 array.
`default_nettype none

module tile_top #(
    parameter int R     = 4,
    parameter int C     = 4,
    parameter int K_MAX = 64
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic [15:0]          cfg_k_i,
    input  logic                 start_i,
    output logic                 busy_o,
    output logic                 done_o,
    output logic                 err_o,
    output logic [2:0]           err_code_o,
    input  logic signed [7:0]    s_axis_a_tdata,
    input  logic                 s_axis_a_tvalid,
    output logic                 s_axis_a_tready,
    input  logic                 s_axis_a_tlast,
    input  logic signed [7:0]    s_axis_b_tdata,
    input  logic                 s_axis_b_tvalid,
    output logic                 s_axis_b_tready,
    input  logic                 s_axis_b_tlast,
    output logic signed [31:0]   m_axis_c_tdata,
    output logic                 m_axis_c_tvalid,
    input  logic                 m_axis_c_tready,
    output logic                 m_axis_c_tlast
);
    typedef enum logic [2:0] {
        ST_IDLE, ST_LOAD, ST_COMPUTE, ST_DRAIN, ST_STORE
    } state_t;
    state_t state;

    logic [15:0] k_q, t_q;
    logic [15:0] a_count, b_count, c_count;

    logic signed [7:0] mem_a [0:R-1][0:K_MAX-1];
    logic signed [7:0] mem_b [0:K_MAX-1][0:C-1];

    logic [8*R-1:0]    a_vec;
    logic [8*C-1:0]    b_vec;
    logic [32*R*C-1:0] acc_o;
    logic              arr_clr, arr_en;

    logic signed [31:0] c_word [0:R*C-1];

    localparam int AW = (R <= 1) ? 1 : $clog2(R);
    localparam int BW = (C <= 1) ? 1 : $clog2(C);
    localparam int KW = (K_MAX <= 1) ? 1 : $clog2(K_MAX);
    localparam int CW = (R * C <= 1) ? 1 : $clog2(R * C);

    assign err_o  = |err_code_o;
    assign busy_o = (state != ST_IDLE);

    wire k_ok = (cfg_k_i >= 16'd1) && (cfg_k_i <= K_MAX[15:0]);
    wire a_fire = s_axis_a_tvalid && s_axis_a_tready;
    wire b_fire = s_axis_b_tvalid && s_axis_b_tready;
    wire c_fire = m_axis_c_tvalid && m_axis_c_tready;

    assign arr_clr = (!rst_n) || (state == ST_IDLE) || (state == ST_LOAD);
    assign arr_en  = (state == ST_COMPUTE);

    wire [15:0] a_need  = R[15:0] * k_q;
    wire [15:0] b_need  = C[15:0] * k_q;
    wire [15:0] c_lastn = 16'(R * C - 1);

    assign s_axis_a_tready = (state == ST_LOAD) && (a_count < a_need);
    assign s_axis_b_tready = (state == ST_LOAD) && (b_count < b_need);
    assign m_axis_c_tvalid = (state == ST_STORE);
    assign m_axis_c_tlast  = (state == ST_STORE) && (c_count == c_lastn);
    assign m_axis_c_tdata  = c_word[c_count[CW-1:0]];

    genvar gn, gi, gj;
    generate
        for (gn = 0; gn < R * C; gn++) begin : g_c
            assign c_word[gn] = signed'(acc_o[32*gn +: 32]);
        end
    endgenerate

    wire feed = (state == ST_COMPUTE) && (t_q < k_q) && (t_q < K_MAX[15:0]);
    generate
        for (gi = 0; gi < R; gi++) begin : g_a
            assign a_vec[8*gi +: 8] = feed ? $unsigned(mem_a[gi][t_q[KW-1:0]]) : 8'd0;
        end
        for (gj = 0; gj < C; gj++) begin : g_b
            assign b_vec[8*gj +: 8] = feed ? $unsigned(mem_b[t_q[KW-1:0]][gj]) : 8'd0;
        end
    endgenerate

    array #(.R(R), .C(C)) u_array (
        .clk   (clk),
        .clr   (arr_clr),
        .en    (arr_en),
        .valid (feed),
        .a_vec (a_vec),
        .b_vec (b_vec),
        .acc_o (acc_o)
    );

    wire [15:0] a_next = a_count + (a_fire ? 16'd1 : 16'd0);
    wire [15:0] b_next = b_count + (b_fire ? 16'd1 : 16'd0);
    wire [15:0] compute_len = k_q + R[15:0] + C[15:0] - 16'd2;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            state      <= ST_IDLE;
            done_o     <= 1'b0;
            err_code_o <= 3'b000;
            k_q        <= 16'd1;
            t_q        <= 16'd0;
            a_count    <= 16'd0;
            b_count    <= 16'd0;
            c_count    <= 16'd0;
        end else begin
            done_o <= 1'b0;
            unique case (state)
                ST_IDLE: begin
                    a_count <= 16'd0;
                    b_count <= 16'd0;
                    c_count <= 16'd0;
                    t_q     <= 16'd0;
                    if (start_i) begin
                        if (k_ok) begin
                            k_q        <= cfg_k_i;
                            err_code_o <= 3'b000;
                            state      <= ST_LOAD;
                        end else begin
                            err_code_o[0] <= 1'b1;
                        end
                    end
                end
                ST_LOAD: begin
                    if (a_fire) begin
                        mem_a[AW'(a_count / k_q)][KW'(a_count % k_q)] <= s_axis_a_tdata;
                        if (s_axis_a_tlast != (a_count == a_need - 16'd1))
                            err_code_o[1] <= 1'b1;
                        a_count <= a_next;
                    end
                    if (b_fire) begin
                        mem_b[KW'(b_count / C[15:0])][BW'(b_count % C[15:0])] <= s_axis_b_tdata;
                        if (s_axis_b_tlast != (b_count == b_need - 16'd1))
                            err_code_o[2] <= 1'b1;
                        b_count <= b_next;
                    end
                    if ((a_next >= a_need) && (b_next >= b_need)) begin
                        state <= ST_COMPUTE;
                        t_q   <= 16'd0;
                    end
                end
                ST_COMPUTE: begin
                    if (t_q + 16'd1 >= compute_len) begin
                        state <= ST_DRAIN;
                    end else begin
                        t_q <= t_q + 16'd1;
                    end
                end
                ST_DRAIN: begin
                    state   <= ST_STORE;
                    c_count <= 16'd0;
                end
                ST_STORE: begin
                    if (c_fire) begin
                        if (c_count == c_lastn) begin
                            state  <= ST_IDLE;
                            done_o <= 1'b1;
                        end else begin
                            c_count <= c_count + 16'd1;
                        end
                    end
                end
                default: state <= ST_IDLE;
            endcase
        end
    end
endmodule

`default_nettype wire
