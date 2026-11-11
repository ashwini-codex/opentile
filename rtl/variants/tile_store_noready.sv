// Broken tile_top: C tdata changes while valid && !tready (O8 failure demo).
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
    logic signed [31:0] corrupt_q;

    assign err_o  = |err_code_o;
    assign busy_o = (state != ST_IDLE);

    wire k_ok = (cfg_k_i >= 16'd1) && (cfg_k_i <= K_MAX[15:0]);
    wire a_fire = s_axis_a_tvalid && s_axis_a_tready;
    wire b_fire = s_axis_b_tvalid && s_axis_b_tready;
    wire c_fire = m_axis_c_tvalid && m_axis_c_tready;

    assign arr_clr = (!rst_n) || (state == ST_IDLE) || (state == ST_LOAD);
    assign arr_en  = (state == ST_COMPUTE);

    assign s_axis_a_tready = (state == ST_LOAD) && (a_count < R * k_q);
    assign s_axis_b_tready = (state == ST_LOAD) && (b_count < C * k_q);
    assign m_axis_c_tvalid = (state == ST_STORE);
    assign m_axis_c_tlast  = (state == ST_STORE) && (c_count == R * C - 1);
    assign m_axis_c_tdata  = c_word[c_count] ^ ((state == ST_STORE && !m_axis_c_tready) ? corrupt_q : 32'sd0);

    genvar gn, gi, gj;
    generate
        for (gn = 0; gn < R * C; gn++) begin : g_c
            assign c_word[gn] = signed'(acc_o[32*gn +: 32]);
        end
    endgenerate

    wire feed = (state == ST_COMPUTE) && (t_q < k_q) && (t_q < K_MAX[15:0]);
    generate
        for (gi = 0; gi < R; gi++) begin : g_a
            assign a_vec[8*gi +: 8] = feed ? $unsigned(mem_a[gi][t_q]) : 8'd0;
        end
        for (gj = 0; gj < C; gj++) begin : g_b
            assign b_vec[8*gj +: 8] = feed ? $unsigned(mem_b[t_q][gj]) : 8'd0;
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
            corrupt_q  <= 32'sh0000_0001;
        end else begin
            done_o <= 1'b0;
            if (state == ST_STORE && !m_axis_c_tready)
                corrupt_q <= {corrupt_q[30:0], corrupt_q[31]};
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
                        mem_a[a_count / k_q][a_count % k_q] <= s_axis_a_tdata;
                        if (s_axis_a_tlast != (a_count == R * k_q - 16'd1))
                            err_code_o[1] <= 1'b1;
                        a_count <= a_next;
                    end
                    if (b_fire) begin
                        mem_b[b_count / C[15:0]][b_count % C[15:0]] <= s_axis_b_tdata;
                        if (s_axis_b_tlast != (b_count == C * k_q - 16'd1))
                            err_code_o[2] <= 1'b1;
                        b_count <= b_next;
                    end
                    if ((a_next >= R * k_q) && (b_next >= C * k_q)) begin
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
                        if (c_count == R * C - 1) begin
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
